import { PageSizeSelector } from "@/components/page-size-selector";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { buildPageWindow } from "@/components/pagination-window";
import { cn } from "@/lib/utils";
import { DoubleArrowLeftIcon, DoubleArrowRightIcon } from "@radix-ui/react-icons";

interface PagePaginationProps {
  currentPage: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
  basePath?: string;
  /** 추가 쿼리 (예: location=uuid). `&` 없이 key=value&key2=value 형태 */
  extraQuery?: string;
}

export function PagePagination({
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  basePath = "/dashboard",
  extraQuery,
}: PagePaginationProps) {
  const hasNextPage = currentPage < totalPages;
  const hasPreviousPage = currentPage > 1;

  const suffix = extraQuery?.trim() ? `&${extraQuery.trim()}` : "";

  const buildUrl = (page: number) =>
    `${basePath}?page=${page}&size=${pageSize}${suffix}`;

  const pages = buildPageWindow(currentPage, totalPages);

  return (
    <div className="flex items-center justify-between my-4">
      <div className="text-sm text-gray-600">
        {totalItems === 0 ? (
          <>Showing 0 of 0 results</>
        ) : (
          <>
            전체 {totalItems}건
          </>
        )}
      </div>

      <Pagination className="mx-0 w-auto justify-end">
        <PaginationContent>
          <PaginationItem className={cn(!hasPreviousPage && "pointer-events-none opacity-50")}>
            <PaginationLink
              href={buildUrl(1)}
              size="icon"
              className="border-0 shadow-none"
              aria-label="First page"
            >
              <DoubleArrowLeftIcon className="h-4 w-4" />
            </PaginationLink>
          </PaginationItem>

          <PaginationItem className={cn(!hasPreviousPage && "pointer-events-none opacity-50")}>
            <PaginationPrevious
              href={buildUrl(currentPage - 1)}
              text="이전"
              className="border-0 shadow-none"
            />
          </PaginationItem>

          {pages.map((p, idx) =>
            p === "ellipsis" ? (
              <PaginationItem key={`e-${idx}`}>
                <PaginationEllipsis />
              </PaginationItem>
            ) : (
              <PaginationItem key={p}>
                <PaginationLink
                  href={buildUrl(p)}
                  isActive={p === currentPage}
                  size="icon"
                >
                  {p}
                </PaginationLink>
              </PaginationItem>
            ),
          )}

          <PaginationItem className={cn(!hasNextPage && "pointer-events-none opacity-50")}>
            <PaginationNext
              href={buildUrl(currentPage + 1)}
              text="다음"
              className="border-0 shadow-none"
            />
          </PaginationItem>

          <PaginationItem className={cn(!hasNextPage && "pointer-events-none opacity-50")}>
            <PaginationLink
              href={buildUrl(totalPages)}
              size="icon"
              className="border-0 shadow-none"
              aria-label="Last page"
            >
              <DoubleArrowRightIcon className="h-4 w-4" />
            </PaginationLink>
          </PaginationItem>
        </PaginationContent>
      </Pagination>
      <PageSizeSelector currentSize={pageSize} basePath={basePath} extraQuery={extraQuery} />
    </div>
  );
}
