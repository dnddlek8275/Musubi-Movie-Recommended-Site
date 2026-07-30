export function SummaryCard({ label, value, note, tone = "default" }) { return <article className={`admin-summary-card tone-${tone}`}><span>{label}</span><strong>{value ?? "—"}</strong>{note && <small>{note}</small>}</article>; }
export function LoadingState() { return <div className="admin-state">데이터를 불러오는 중입니다…</div>; }
export function ErrorState({ message }) { return <div className="admin-state admin-error" role="alert">{message}</div>; }
export function EmptyState({ message = "표시할 데이터가 없습니다." }) { return <div className="admin-state">{message}</div>; }
export function Pagination({ page, totalPages, onChange }) { if (totalPages <= 1) return null; return <nav className="admin-pagination" aria-label="페이지 이동"><button disabled={page <= 1} onClick={() => onChange(page - 1)}>이전</button><span>{page} / {totalPages}</span><button disabled={page >= totalPages} onClick={() => onChange(page + 1)}>다음</button></nav>; }
