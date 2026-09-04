/** 큐(scheduler_job_queue) 상태 — API 값 */
export type SchedulerQueueStatus =
  | "PENDING"
  | "PROCESSING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLED";

export const QUEUE_STATUS_OPTIONS: { value: SchedulerQueueStatus | ""; label: string }[] = [
  { value: "", label: "전체" },
  { value: "PENDING", label: "실행대기" },
  { value: "PROCESSING", label: "실행중" },
  { value: "SUCCEEDED", label: "완료" },
  { value: "FAILED", label: "실패" },
  { value: "CANCELLED", label: "중지됨" },
];

export function queueStatusLabel(status: string): string {
  const found = QUEUE_STATUS_OPTIONS.find((o) => o.value === status);
  return found?.label ?? status;
}

export function canCancelQueue(status: string): boolean {
  return status === "PENDING" || status === "PROCESSING";
}

export type RegistryEntry = {
  job_key: string;
  title: string | null;
  registered: boolean;
  schedule_count: number;
  description?: string | null;
};

export type SchedulerScheduleRow = {
  id: string;
  job_key: string;
  name: string;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  payload: Record<string, unknown> | null;
  concurrency_key: string | null;
  description: string | null;
  registered: boolean;
};

export type SchedulerQueueRow = {
  id: string;
  job_key: string;
  schedule_id: string | null;
  action: string;
  status: string;
  requested_by_user_id: string | null;
  related_log_id: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type SchedulerQueuePage = {
  items: SchedulerQueueRow[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

/** 스케줄 등록/수정 폼 (timezone은 Asia/Seoul 고정) */
export type SchedulerScheduleFormState = {
  job_key: string;
  name: string;
  cron_expression: string;
  enabled: boolean;
  description: string;
};
