"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRouter } from "next/navigation";
import { MAX_PAGE_SIZE, PAGE_SIZE_OPTIONS } from "@/lib/pagination";

interface PageSizeSelectorProps {
  currentSize: number;
  basePath?: string;
  /** 추가 쿼리 (예: location=uuid). `&` 없이 key=value&key2=value 형태 */
  extraQuery?: string;
}

export function PageSizeSelector({
  currentSize,
  basePath = "/dashboard",
  extraQuery,
}: PageSizeSelectorProps) {
  const router = useRouter();
  const handleSizeChange = (newSize: string) => {
    const size = Math.min(Math.max(1, Number(newSize) || 1), MAX_PAGE_SIZE);
    const suffix = extraQuery?.trim() ? `&${extraQuery.trim()}` : "";
    router.push(`${basePath}?page=1&size=${size}${suffix}`);
  };

  return (
    <div className="flex items-center space-x-2">
      <span className="text-sm text-gray-600">페이지당:</span>
      <Select value={currentSize.toString()} onValueChange={handleSizeChange}>
        <SelectTrigger className="w-20">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {PAGE_SIZE_OPTIONS.map((option) => (
            <SelectItem key={option} value={option.toString()}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
