type PaginationProps = {
  total?: number;
  limit?: number;
  offset?: number;
  onPageChange?: (offset: number) => void;
};

export function Pagination({ total, limit = 20, offset = 0, onPageChange }: PaginationProps) {
  if (!total || total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pageCount = Math.ceil(total / limit);
  return (
    <div className="pagination">
      <button type="button" disabled={page <= 1} onClick={() => onPageChange?.(Math.max(0, offset - limit))}>
        上一页
      </button>
      <span>
        {page} / {pageCount}
      </span>
      <button type="button" disabled={page >= pageCount} onClick={() => onPageChange?.(offset + limit)}>
        下一页
      </button>
    </div>
  );
}
