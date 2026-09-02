"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { formatDateTimeInSeoul } from "@/lib/date-utils";
import {
  canCancelQueue,
  QUEUE_STATUS_OPTIONS,
  queueStatusLabel,
  type SchedulerJobFormState,
  type SchedulerJobRow,
  type SchedulerQueuePage,
  type SchedulerQueueRow,
} from "@/lib/scheduler-status";
import { PagePagination } from "@/components/page-pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Field, FieldGroup, FieldLabel, FieldSet } from "@/components/ui/field";

async function readApiError(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  try {
    const j = JSON.parse(text) as { detail?: string | { msg?: string }[] };
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) {
      return j.detail.map((d) => (typeof d === "object" && d?.msg ? d.msg : String(d))).join(", ");
    }
  } catch {
    /* ignore */
  }
  return text || `요청 실패 (HTTP ${res.status})`;
}

function StatusBadge({ status }: { status: string }) {
  const label = queueStatusLabel(status);
  let cls = "bg-muted text-muted-foreground";
  if (status === "PENDING") cls = "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
  if (status === "PROCESSING") cls = "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200";
  if (status === "SUCCEEDED") cls = "bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200";
  if (status === "FAILED") cls = "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200";
  if (status === "CANCELLED") cls = "bg-gray-200 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

const defaultJobForm = (jobKey = ""): SchedulerJobFormState => ({
  job_key: jobKey,
  title: "",
  enabled: true,
  cron_hour: 3,
  cron_minute: 0,
  timezone: "Asia/Seoul",
  description: "",
});

export default function AdminSchedulerPage() {
  const router = useRouter();
  const params = useSearchParams();
  const tab = params.get("tab") === "queue" ? "queue" : "jobs";

  const page = Number(params.get("page")) || 1;
  const size = Number(params.get("size")) || 20;
  const queueStatus = params.get("status") ?? "";
  const queueJobKey = params.get("job_key") ?? "";
  const queueQ = params.get("q") ?? "";

  const jobsQ = params.get("jobs_q") ?? "";

  const [queueStatusSelect, setQueueStatusSelect] = useState(queueStatus || "__all__");
  useEffect(() => {
    setQueueStatusSelect(queueStatus || "__all__");
  }, [queueStatus]);

  const [jobs, setJobs] = useState<SchedulerJobRow[]>([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsError, setJobsError] = useState("");

  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [queueResult, setQueueResult] = useState<SchedulerQueuePage>({
    items: [],
    total: 0,
    page: 1,
    size: 20,
    pages: 1,
  });

  const [jobDialogOpen, setJobDialogOpen] = useState(false);
  const [jobDialogMode, setJobDialogMode] = useState<"create" | "edit">("create");
  const [jobForm, setJobForm] = useState<SchedulerJobFormState>(() => defaultJobForm());
  const [registeredJobKeys, setRegisteredJobKeys] = useState<string[]>([]);
  const [editJobKey, setEditJobKey] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SchedulerJobRow | null>(null);
  const [busy, setBusy] = useState(false);

  const queueExtraQuery = useMemo(() => {
    const q = new URLSearchParams();
    q.set("tab", "queue");
    if (queueStatus) q.set("status", queueStatus);
    if (queueJobKey.trim()) q.set("job_key", queueJobKey.trim());
    if (queueQ.trim()) q.set("q", queueQ.trim());
    return q.toString();
  }, [queueStatus, queueJobKey, queueQ]);

  const loadJobs = useCallback(async () => {
    setJobsLoading(true);
    setJobsError("");
    const sp = new URLSearchParams();
    if (jobsQ.trim()) sp.set("q", jobsQ.trim());
    try {
      const res = await fetch(`/api/admin/scheduler/jobs?${sp.toString()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(await readApiError(res));
      setJobs((await res.json()) as SchedulerJobRow[]);
    } catch (e) {
      setJobsError(e instanceof Error ? e.message : "Job 목록 조회 실패");
    } finally {
      setJobsLoading(false);
    }
  }, [jobsQ]);

  const loadQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError("");
    const sp = new URLSearchParams();
    sp.set("page", String(page));
    sp.set("size", String(size));
    if (queueStatus) sp.set("status", queueStatus);
    if (queueJobKey.trim()) sp.set("job_key", queueJobKey.trim());
    if (queueQ.trim()) sp.set("q", queueQ.trim());
    try {
      const res = await fetch(`/api/admin/scheduler/queue?${sp.toString()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(await readApiError(res));
      setQueueResult((await res.json()) as SchedulerQueuePage);
    } catch (e) {
      setQueueError(e instanceof Error ? e.message : "실행 이력 조회 실패");
    } finally {
      setQueueLoading(false);
    }
  }, [page, size, queueStatus, queueJobKey, queueQ]);

  useEffect(() => {
    if (tab === "jobs") void loadJobs();
  }, [tab, loadJobs]);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/admin/scheduler/job-keys", { cache: "no-store" });
        if (!res.ok) return;
        const keys = (await res.json()) as string[];
        setRegisteredJobKeys(keys);
      } catch {
        /* ignore — create dialog falls back to empty list */
      }
    })();
  }, []);

  useEffect(() => {
    if (tab === "queue") void loadQueue();
  }, [tab, loadQueue]);

  const openCreateJob = () => {
    setJobDialogMode("create");
    setEditJobKey(null);
    setJobForm(defaultJobForm(registeredJobKeys[0] ?? ""));
    setJobDialogOpen(true);
  };

  const openEditJob = (row: SchedulerJobRow) => {
    setJobDialogMode("edit");
    setEditJobKey(row.job_key);
    setJobForm({
      job_key: row.job_key,
      title: row.title,
      enabled: row.enabled,
      cron_hour: row.cron_hour,
      cron_minute: row.cron_minute,
      timezone: row.timezone,
      description: row.description ?? "",
    });
    setJobDialogOpen(true);
  };

  const saveJob = async () => {
    setBusy(true);
    try {
      const body = {
        title: jobForm.title.trim(),
        enabled: jobForm.enabled,
        cron_hour: Number(jobForm.cron_hour),
        cron_minute: Number(jobForm.cron_minute),
        timezone: jobForm.timezone.trim() || "Asia/Seoul",
        description: jobForm.description.trim() || null,
      };
      if (jobDialogMode === "create") {
        const res = await fetch("/api/admin/scheduler/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            job_key: jobForm.job_key,
            ...body,
          }),
        });
        if (!res.ok) throw new Error(await readApiError(res));
        toast.success("Job이 등록되었습니다.");
      } else if (editJobKey) {
        const res = await fetch(
          `/api/admin/scheduler/jobs/${encodeURIComponent(editJobKey)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        );
        if (!res.ok) throw new Error(await readApiError(res));
        toast.success("Job이 수정되었습니다.");
      }
      setJobDialogOpen(false);
      await loadJobs();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  };

  const confirmDeleteJob = async () => {
    if (!deleteTarget) return;
    setBusy(true);
    try {
      const res = await fetch(
        `/api/admin/scheduler/jobs/${encodeURIComponent(deleteTarget.job_key)}`,
        { method: "DELETE" },
      );
      if (!res.ok && res.status !== 204) throw new Error(await readApiError(res));
      toast.success("Job이 삭제되었습니다.");
      setDeleteTarget(null);
      await loadJobs();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setBusy(false);
    }
  };

  const enqueueRun = async (jobKey: string) => {
    setBusy(true);
    try {
      const res = await fetch(
        `/api/admin/scheduler/jobs/${encodeURIComponent(jobKey)}/enqueue-run`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await readApiError(res));
      toast.success("즉시 실행이 큐에 등록되었습니다.");
      if (tab === "queue") await loadQueue();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "실행 요청 실패");
    } finally {
      setBusy(false);
    }
  };

  const cancelQueue = async (row: SchedulerQueueRow) => {
    setBusy(true);
    try {
      const res = await fetch(
        `/api/admin/scheduler/queue/${row.id}/cancel`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(await readApiError(res));
      toast.success("실행이 중지되었습니다.");
      await loadQueue();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "중지 실패");
    } finally {
      setBusy(false);
    }
  };

  const onJobsSearch = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const q = new URLSearchParams();
    q.set("tab", "jobs");
    const jq = String(fd.get("jobs_q") ?? "").trim();
    if (jq) q.set("jobs_q", jq);
    router.push(`/admin/scheduler?${q.toString()}`);
  };

  const onQueueSearch = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const q = new URLSearchParams();
    q.set("tab", "queue");
    q.set("page", "1");
    q.set("size", String(size));
    const st = queueStatusSelect === "__all__" ? "" : queueStatusSelect;
    const jk = String(fd.get("job_key") ?? "").trim();
    const qq = String(fd.get("q") ?? "").trim();
    if (st) q.set("status", st);
    if (jk) q.set("job_key", jk);
    if (qq) q.set("q", qq);
    router.push(`/admin/scheduler?${q.toString()}`);
  };

  const setTab = (value: string) => {
    const q = new URLSearchParams(params.toString());
    q.set("tab", value);
    if (value === "jobs") {
      q.delete("page");
    } else if (!q.get("page")) {
      q.set("page", "1");
    }
    router.push(`/admin/scheduler?${q.toString()}`);
  };

  const totalQueuePages = Math.max(1, Math.ceil((queueResult.total || 0) / size));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold">스케줄 관리</h2>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="jobs">Job 정의</TabsTrigger>
          <TabsTrigger value="queue">실행 이력</TabsTrigger>
        </TabsList>

        <TabsContent value="jobs" className="space-y-4">
          <section className="rounded-lg bg-white p-6 shadow-lg dark:bg-gray-900">
            <form onSubmit={onJobsSearch} className="mb-4 flex flex-wrap items-end gap-3">
              <Field className="w-[280px]">
                <FieldLabel htmlFor="jobs_q">검색 (키·제목)</FieldLabel>
                <Input id="jobs_q" name="jobs_q" defaultValue={jobsQ} placeholder="job_key 또는 제목" />
              </Field>
              <Button type="submit" variant="secondary">
                검색
              </Button>
              <Button type="button" variant="outline" onClick={() => router.push("/admin/scheduler?tab=jobs")}>
                초기화
              </Button>
              <div className="flex-1" />
              <Button type="button" onClick={openCreateJob}>
                Job 등록
              </Button>
            </form>

            {jobsError ? <p className="text-sm text-destructive">{jobsError}</p> : null}

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job 키</TableHead>
                  <TableHead>제목</TableHead>
                  <TableHead>활성</TableHead>
                  <TableHead>스케줄</TableHead>
                  <TableHead>타임존</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobsLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      불러오는 중…
                    </TableCell>
                  </TableRow>
                ) : jobs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      등록된 Job이 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  jobs.map((row) => (
                    <TableRow key={row.job_key}>
                      <TableCell className="font-mono text-sm">{row.job_key}</TableCell>
                      <TableCell>{row.title}</TableCell>
                      <TableCell>{row.enabled ? "Y" : "N"}</TableCell>
                      <TableCell>
                        {String(row.cron_hour).padStart(2, "0")}:{String(row.cron_minute).padStart(2, "0")}
                      </TableCell>
                      <TableCell>{row.timezone}</TableCell>
                      <TableCell className="text-right space-x-1">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => void enqueueRun(row.job_key)}
                        >
                          즉시 실행
                        </Button>
                        <Button type="button" size="sm" variant="secondary" onClick={() => openEditJob(row)}>
                          수정
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="destructive"
                          onClick={() => setDeleteTarget(row)}
                        >
                          삭제
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </section>
        </TabsContent>

        <TabsContent value="queue" className="space-y-4">
          <section className="rounded-lg bg-white p-6 shadow-lg dark:bg-gray-900">
            <form onSubmit={onQueueSearch} className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-6">
              <Field>
                <FieldLabel htmlFor="queue_status">상태</FieldLabel>
                <Select value={queueStatusSelect} onValueChange={setQueueStatusSelect}>
                  <SelectTrigger id="queue_status">
                    <SelectValue placeholder="전체" />
                  </SelectTrigger>
                  <SelectContent>
                    {QUEUE_STATUS_OPTIONS.map((o) => (
                      <SelectItem key={o.value || "__all__"} value={o.value || "__all__"}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="queue_job_key">Job 키</FieldLabel>
                <Input id="queue_job_key" name="job_key" defaultValue={queueJobKey} />
              </Field>
              <Field className="lg:col-span-2">
                <FieldLabel htmlFor="queue_q">검색 (Job 키)</FieldLabel>
                <Input id="queue_q" name="q" defaultValue={queueQ} />
              </Field>
              <div className="flex items-end gap-2 lg:col-span-2">
                <Button type="submit" variant="secondary">
                  검색
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => router.push("/admin/scheduler?tab=queue&page=1&size=20")}
                >
                  초기화
                </Button>
              </div>
            </form>

            {queueError ? <p className="text-sm text-destructive">{queueError}</p> : null}

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Job 키</TableHead>
                  <TableHead>동작</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>요청 시각</TableHead>
                  <TableHead>시작</TableHead>
                  <TableHead>종료</TableHead>
                  <TableHead>오류</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queueLoading ? (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center text-muted-foreground">
                      불러오는 중…
                    </TableCell>
                  </TableRow>
                ) : queueResult.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center text-muted-foreground">
                      실행 이력이 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  queueResult.items.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{row.id}</TableCell>
                      <TableCell className="font-mono text-sm">{row.job_key}</TableCell>
                      <TableCell>{row.action}</TableCell>
                      <TableCell>
                        <StatusBadge status={row.status} />
                      </TableCell>
                      <TableCell>{formatDateTimeInSeoul(row.created_at)}</TableCell>
                      <TableCell>{formatDateTimeInSeoul(row.started_at)}</TableCell>
                      <TableCell>{formatDateTimeInSeoul(row.finished_at)}</TableCell>
                      <TableCell className="max-w-[200px] truncate text-xs" title={row.error_message ?? ""}>
                        {row.error_message ?? "-"}
                      </TableCell>
                      <TableCell className="text-right">
                        {canCancelQueue(row.status) ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            disabled={busy}
                            onClick={() => void cancelQueue(row)}
                          >
                            중지
                          </Button>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>

            <PagePagination
              currentPage={page}
              totalPages={totalQueuePages}
              pageSize={size}
              totalItems={queueResult.total}
              basePath="/admin/scheduler"
              extraQuery={queueExtraQuery}
            />
          </section>
        </TabsContent>
      </Tabs>

      <Dialog open={jobDialogOpen} onOpenChange={setJobDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{jobDialogMode === "create" ? "Job 등록" : "Job 수정"}</DialogTitle>
          </DialogHeader>
          <FieldGroup>
            <FieldSet className="space-y-3">
              {jobDialogMode === "create" ? (
                <Field>
                  <FieldLabel>Job 키</FieldLabel>
                  <Select
                    value={jobForm.job_key}
                    onValueChange={(v) => setJobForm((f) => ({ ...f, job_key: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {registeredJobKeys.map((k) => (
                        <SelectItem key={k} value={k}>
                          {k}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              ) : (
                <Field>
                  <FieldLabel>Job 키</FieldLabel>
                  <Input value={editJobKey ?? ""} disabled />
                </Field>
              )}
              <Field>
                <FieldLabel>제목</FieldLabel>
                <Input
                  value={jobForm.title}
                  onChange={(e) => setJobForm((f) => ({ ...f, title: e.target.value }))}
                />
              </Field>
              <Field className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="job_enabled"
                  checked={jobForm.enabled}
                  onChange={(e) => setJobForm((f) => ({ ...f, enabled: e.target.checked }))}
                />
                <Label htmlFor="job_enabled">활성 (cron 자동 실행)</Label>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field>
                  <FieldLabel>시 (0–23)</FieldLabel>
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={jobForm.cron_hour}
                    onChange={(e) =>
                      setJobForm((f) => ({ ...f, cron_hour: Number(e.target.value) }))
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel>분 (0–59)</FieldLabel>
                  <Input
                    type="number"
                    min={0}
                    max={59}
                    value={jobForm.cron_minute}
                    onChange={(e) =>
                      setJobForm((f) => ({ ...f, cron_minute: Number(e.target.value) }))
                    }
                  />
                </Field>
              </div>
              <Field>
                <FieldLabel>타임존</FieldLabel>
                <Input
                  value={jobForm.timezone}
                  onChange={(e) => setJobForm((f) => ({ ...f, timezone: e.target.value }))}
                />
              </Field>
              <Field>
                <FieldLabel>설명</FieldLabel>
                <Input
                  value={jobForm.description}
                  onChange={(e) => setJobForm((f) => ({ ...f, description: e.target.value }))}
                />
              </Field>
            </FieldSet>
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setJobDialogOpen(false)}>
              취소
            </Button>
            <Button type="button" disabled={busy || !jobForm.title.trim()} onClick={() => void saveJob()}>
              저장
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteTarget !== null} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Job 삭제</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            <span className="font-mono">{deleteTarget?.job_key}</span> 정의를 삭제할까요?
          </p>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              취소
            </Button>
            <Button type="button" variant="destructive" disabled={busy} onClick={() => void confirmDeleteJob()}>
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
