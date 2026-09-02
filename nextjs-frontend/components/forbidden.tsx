import Link from "next/link";

import { Button } from "@/components/ui/button";

export function Forbidden() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 text-center">
      <h1 className="text-2xl font-semibold">403 — 권한 없음</h1>
      <p className="max-w-md text-muted-foreground">
        이 페이지에 접근할 권한이 없습니다. 관리자에게 역할 부여를 요청하세요.
      </p>
      <Button asChild variant="outline">
        <Link href="/">홈으로</Link>
      </Button>
    </div>
  );
}
