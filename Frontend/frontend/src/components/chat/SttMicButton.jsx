import { useEffect, useRef, useState } from 'react';

import { transcribeAudio } from '../../api.js';

const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/ogg;codecs=opus',
];
const SILENCE_SUBMIT_MS = 5000;
const VOICE_RMS_THRESHOLD = 0.03;

function selectMimeType() {
  if (typeof MediaRecorder === 'undefined') return '';
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) || '';
}

export default function SttMicButton({ disabled = false, onTranscript, onError }) {
  const [status, setStatus] = useState('idle');
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const abortRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const audioContextRef = useRef(null);
  const silenceFrameRef = useRef(null);
  const stopAndTranscribeRef = useRef(null);

  const stopSilenceMonitor = () => {
    if (silenceTimerRef.current) window.clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = null;
    if (silenceFrameRef.current) window.cancelAnimationFrame(silenceFrameRef.current);
    silenceFrameRef.current = null;
    audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
  };

  const armSilenceSubmit = () => {
    if (silenceTimerRef.current) window.clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = window.setTimeout(() => {
      silenceTimerRef.current = null;
      void stopAndTranscribeRef.current?.();
    }, SILENCE_SUBMIT_MS);
  };

  const startSilenceMonitor = (stream) => {
    armSilenceSubmit();
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;

    const context = new AudioContextClass();
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    context.createMediaStreamSource(stream).connect(analyser);
    const samples = new Uint8Array(analyser.fftSize);
    audioContextRef.current = context;

    const detectVoice = () => {
      analyser.getByteTimeDomainData(samples);
      let squareSum = 0;
      for (const sample of samples) {
        const normalized = (sample - 128) / 128;
        squareSum += normalized * normalized;
      }
      const rms = Math.sqrt(squareSum / samples.length);
      if (rms >= VOICE_RMS_THRESHOLD) armSilenceSubmit();
      silenceFrameRef.current = window.requestAnimationFrame(detectVoice);
    };
    detectVoice();
  };

  const stopTracks = () => {
    stopSilenceMonitor();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  useEffect(() => {
    if (status !== 'recording') return undefined;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [status]);

  useEffect(() => () => {
    abortRef.current?.abort();
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    stopTracks();
  }, []);

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      onError?.('이 브라우저는 음성 녹음을 지원하지 않습니다.');
      return;
    }

    try {
      setStatus('requesting');
      setElapsed(0);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = selectMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.addEventListener('dataavailable', (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      });
      recorder.start();
      startSilenceMonitor(stream);
      setStatus('recording');
    } catch (error) {
      stopTracks();
      setStatus('idle');
      onError?.(
        error?.name === 'NotAllowedError'
          ? '마이크 권한이 필요합니다. 브라우저 설정에서 허용해주세요.'
          : '마이크를 시작할 수 없습니다.'
      );
    }
  };

  const stopAndTranscribe = async () => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state !== 'recording') return;
    stopSilenceMonitor();

    try {
      const audioBlob = await new Promise((resolve, reject) => {
        recorder.addEventListener('error', () => reject(new Error('녹음에 실패했습니다.')), {
          once: true,
        });
        recorder.addEventListener('stop', () => {
          resolve(new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' }));
        }, { once: true });
        recorder.stop();
      });
      stopTracks();
      recorderRef.current = null;
      chunksRef.current = [];
      setStatus('transcribing');
      abortRef.current = new AbortController();
      const text = await transcribeAudio(audioBlob, abortRef.current.signal);
      // transcribeAudio는 state=success이고 data.text가 있을 때만 반환한다.
      // failure/error에서는 아래 콜백을 실행하지 않아 기존 채팅 API 호출을 차단한다.
      onTranscript?.(text);
    } catch (error) {
      if (error?.name !== 'AbortError') onError?.(error.message || '음성 변환에 실패했습니다.');
    } finally {
      abortRef.current = null;
      stopTracks();
      setStatus('idle');
    }
  };

  stopAndTranscribeRef.current = stopAndTranscribe;

  const recording = status === 'recording';
  const working = status === 'requesting' || status === 'transcribing';
  const label = recording
    ? `녹음 중 ${elapsed}초 — 5초 무음 시 자동 전송`
    : status === 'requesting'
      ? '마이크 권한 확인 중'
      : status === 'transcribing'
        ? '음성을 텍스트로 변환 중'
        : '음성으로 입력';

  return (
    <button
      className={`chat-send ${recording ? 'chat-send--recording' : ''}`}
      type="button"
      onClick={recording ? stopAndTranscribe : startRecording}
      disabled={disabled || working}
      aria-label={label}
      title={label}
      aria-pressed={recording}
    >
      {working ? (
        <span className="chat-send__loader" aria-hidden="true" />
      ) : recording ? (
        <span className="chat-send__stop" aria-hidden="true" />
      ) : (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 15a3.5 3.5 0 0 0 3.5-3.5v-5a3.5 3.5 0 0 0-7 0v5A3.5 3.5 0 0 0 12 15Z" />
          <path d="M18.5 11.5a6.5 6.5 0 0 1-13 0M12 18v3M9 21h6" />
        </svg>
      )}
    </button>
  );
}
