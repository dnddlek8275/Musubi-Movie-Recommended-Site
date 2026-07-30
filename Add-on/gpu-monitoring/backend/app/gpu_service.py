import random
from datetime import datetime
from zoneinfo import ZoneInfo

import psutil

from .schemas import GpuInfo, GpuProcess

try:
    import pynvml
except ImportError:  # The API remains available even before the optional driver binding is installed.
    pynvml = None  # type: ignore[assignment]


MB = 1024 * 1024


class GpuUnavailableError(RuntimeError):
    pass


class GpuNotFoundError(IndexError):
    pass


class GpuService:
    def __init__(self, use_mock_data: bool = False) -> None:
        self.use_mock_data = use_mock_data
        self.nvml_available = False
        self.driver_version: str | None = None

    def initialize(self) -> None:
        if self.use_mock_data:
            self.nvml_available = True
            self.driver_version = "550.54.15 (mock)"
            return
        if pynvml is None:
            return
        try:
            pynvml.nvmlInit()
            self.nvml_available = True
            self.driver_version = self._decode(pynvml.nvmlSystemGetDriverVersion())
        except pynvml.NVMLError:
            self.nvml_available = False

    def shutdown(self) -> None:
        if self.nvml_available and not self.use_mock_data and pynvml is not None:
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError:
                pass
        self.nvml_available = False

    def list_gpus(self) -> list[GpuInfo]:
        if self.use_mock_data:
            return [self._mock_gpu(index) for index in range(2)]
        if not self.nvml_available or pynvml is None:
            raise GpuUnavailableError("NVIDIA GPU or NVML is not available")
        try:
            count = pynvml.nvmlDeviceGetCount()
            return [self._read_gpu(index) for index in range(count)]
        except pynvml.NVMLError as exc:
            raise GpuUnavailableError("NVIDIA GPU or NVML is not available") from exc

    def get_gpu(self, index: int) -> GpuInfo:
        if index < 0:
            raise GpuNotFoundError(index)
        gpus = self.list_gpus()
        if index >= len(gpus):
            raise GpuNotFoundError(index)
        return gpus[index]

    def get_processes(self, index: int) -> list[GpuProcess]:
        return self.get_gpu(index).processes

    def _read_gpu(self, index: int) -> GpuInfo:
        assert pynvml is not None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
        except pynvml.NVMLError as exc:
            raise GpuNotFoundError(index) from exc

        memory = self._safe(lambda: pynvml.nvmlDeviceGetMemoryInfo(handle))
        utilization = self._safe(lambda: pynvml.nvmlDeviceGetUtilizationRates(handle))
        used = self._mb(memory.used) if memory else None
        total = self._mb(memory.total) if memory else None
        free = self._mb(memory.free) if memory else None
        return GpuInfo(
            index=index,
            uuid=self._decode(self._safe(lambda: pynvml.nvmlDeviceGetUUID(handle))),
            name=self._decode(self._safe(lambda: pynvml.nvmlDeviceGetName(handle))),
            gpu_usage_percent=float(utilization.gpu) if utilization else None,
            memory_controller_usage_percent=float(utilization.memory) if utilization else None,
            memory_used_mb=used,
            memory_total_mb=total,
            memory_free_mb=free,
            memory_usage_percent=round(used / total * 100, 2) if used is not None and total else None,
            temperature_celsius=self._float_safe(
                lambda: pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            ),
            power_usage_watts=self._scaled_safe(lambda: pynvml.nvmlDeviceGetPowerUsage(handle), 1000),
            power_limit_watts=self._scaled_safe(lambda: pynvml.nvmlDeviceGetEnforcedPowerLimit(handle), 1000),
            fan_speed_percent=self._float_safe(lambda: pynvml.nvmlDeviceGetFanSpeed(handle)),
            graphics_clock_mhz=self._int_safe(
                lambda: pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
            ),
            memory_clock_mhz=self._int_safe(
                lambda: pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
            ),
            driver_version=self.driver_version,
            processes=self._read_processes(handle),
        )

    def _read_processes(self, handle: object) -> list[GpuProcess]:
        assert pynvml is not None
        entries: dict[int, float | None] = {}
        queries = [pynvml.nvmlDeviceGetComputeRunningProcesses]
        graphics_query = getattr(pynvml, "nvmlDeviceGetGraphicsRunningProcesses", None)
        if graphics_query:
            queries.append(graphics_query)
        for query in queries:
            try:
                for process in query(handle):
                    raw_memory = getattr(process, "usedGpuMemory", None)
                    unavailable = getattr(pynvml, "NVML_VALUE_NOT_AVAILABLE", None)
                    memory = None if raw_memory in (None, unavailable) else round(raw_memory / MB, 2)
                    entries[process.pid] = memory
            except pynvml.NVMLError:
                continue
        return [self._process_details(pid, memory) for pid, memory in sorted(entries.items())]

    @staticmethod
    def _process_details(pid: int, used_memory_mb: float | None) -> GpuProcess:
        try:
            process = psutil.Process(pid)
            command = " ".join(process.cmdline()) or None
            return GpuProcess(pid=pid, name=process.name(), command=command, used_memory_mb=used_memory_mb)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return GpuProcess(pid=pid, used_memory_mb=used_memory_mb)

    def _mock_gpu(self, index: int) -> GpuInfo:
        gpu = random.randint(25 + index * 8, 88)
        total = 15360.0
        memory_percent = random.randint(30, 82)
        used = round(total * memory_percent / 100, 2)
        return GpuInfo(
            index=index,
            uuid=f"GPU-MOCK-T4-{index:04d}",
            name="NVIDIA Tesla T4",
            gpu_usage_percent=gpu,
            memory_controller_usage_percent=random.randint(10, 65),
            memory_used_mb=used,
            memory_total_mb=total,
            memory_free_mb=round(total - used, 2),
            memory_usage_percent=memory_percent,
            temperature_celsius=random.randint(48, 78),
            power_usage_watts=round(random.uniform(35, 68), 1),
            power_limit_watts=70.0,
            fan_speed_percent=None,
            graphics_clock_mhz=random.choice([1350, 1590]),
            memory_clock_mhz=5001,
            driver_version=self.driver_version,
            processes=[
                GpuProcess(
                    pid=1200 + index,
                    name="python",
                    command=f"python train_gpu_{index}.py",
                    used_memory_mb=round(used * 0.6, 2),
                )
            ],
        )

    @staticmethod
    def _safe(callback):
        assert pynvml is not None
        try:
            return callback()
        except pynvml.NVMLError:
            return None

    def _float_safe(self, callback) -> float | None:
        value = self._safe(callback)
        return float(value) if value is not None else None

    def _int_safe(self, callback) -> int | None:
        value = self._safe(callback)
        return int(value) if value is not None else None

    def _scaled_safe(self, callback, divisor: float) -> float | None:
        value = self._safe(callback)
        return round(float(value) / divisor, 2) if value is not None else None

    @staticmethod
    def _decode(value: bytes | str | None) -> str | None:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    @staticmethod
    def _mb(value: int) -> float:
        return round(value / MB, 2)


def now_seoul() -> datetime:
    return datetime.now(ZoneInfo("Asia/Seoul"))
