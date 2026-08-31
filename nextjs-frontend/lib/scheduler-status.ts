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

export type SchedulerJobRow = {
  job_key: string;
  title: string;
  enabled: boolean;
  cron_hour: number;
  cron_minute: number;
  timezone: string;
  description: string | null;
};

export type SchedulerQueueRow = {
  id: number;
  job_key: string;
  action: string;
  status: string;
  requested_by_user_id: string | null;
  related_log_id: number | null;
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

/** 코드에 등록된 job_key (백엔드 REGISTERED_JOB_KEYS와 동기) */
export const REGISTERED_JOB_KEYS = ["sample_heartbeat"] as const;

export type RegisteredJobKey = (typeof REGISTERED_JOB_KEYS)[number];

/** Job 등록/수정 폼 (job_key는 API 문자열; 생성 시 REGISTERED_JOB_KEYS 중 선택) */
export type SchedulerJobFormState = {
  job_key: string;
  title: string;
  enabled: boolean;
  cron_hour: number;
  cron_minute: number;
  timezone: string;
  description: string;
};
