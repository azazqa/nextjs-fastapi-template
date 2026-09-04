"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { formatDateTimeInSeoul } from "@/lib/date-utils";
import {
  canCancelQueue,
  QUEUE_STATUS_OPTIONS,
  queueStatusLabel,
  type RegistryEntry,
  type SchedulerQueuePage,
  type SchedulerQueueRow,
  type SchedulerScheduleFormState,
  type SchedulerScheduleRow,
} from "@/lib/scheduler-status";
import { PagePagination } from "@/components/page-pagination";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
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

function formatCronErrorMessage(raw: string): string {
  const cleaned = raw
    .replace(/^Value error,\s*/i, "")
    .replace(/^(invalid cron expression|잘못된 Cron 표현식):\s*/i, "")
    .trim();
  return cleaned ? `잘못된 Cron 표현식: ${cleaned}` : "잘못된 Cron 표현식입니다.";
}

function StatusBadge({ status }: { status: string }) {
  const label = queueStatusLabel(status);
  let cls = "bg-muted text-muted-foreground";
  if (status === "PENDING") cls = "bg-muted text-muted-foreground";
  if (status === "PROCESSING") cls = "bg-secondary text-secondary-foreground";
  if (status === "SUCCEEDED") cls = "bg-primary text-primary-foreground";
  if (status === "FAILED") cls = "bg-destructive/10 text-destructive";
  if (status === "CANCELLED") cls = "bg-secondary text-secondary-foreground";
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

const defaultScheduleForm = (jobKey = ""): SchedulerScheduleFormState => ({
  job_key: jobKey,
  name: "",
  cron_expression: "0 * * * *",
  enabled: true,
  description: "",
});

export default function AdminSchedulerPage() {
  const router = useRouter();
  const params = useSearchParams();
  const tab = params.get("tab") === "queue" ? "queue" : "schedules";

  const page = Number(params.get("page")) || 1;
  const size = Number(params.get("size")) || 20;
  const queueStatus = params.get("status") ?? "";
  const queueJobKey = params.get("job_key") ?? "";
  const queueQ = params.get("q") ?? "";

  const schedulesQ = params.get("schedules_q") ?? "";

  const [queueStatusSelect, setQueueStatusSelect] = useState(queueStatus || "__all__");
  useEffect(() => {
    setQueueStatusSelect(queueStatus || "__all__");
  }, [queueStatus]);

  const [schedules, setSchedules] = useState<SchedulerScheduleRow[]>([]);
  const [schedulesLoading, setSchedulesLoading] = useState(true);
  const [schedulesError, setSchedulesError] = useState("");

  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [queueResult, setQueueResult] = useState<SchedulerQueuePage>({
    items: [],
    total: 0,
    page: 1,
    size: 20,
    pages: 1,
  });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  const [form, setForm] = useState<SchedulerScheduleFormState>(() => defaultScheduleForm());
  const [registry, setRegistry] = useState<RegistryEntry[]>([]);
  const [editId, setEditId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SchedulerScheduleRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [cronPreview, setCronPreview] = useState<string[]>([]);
  const [cronError, setCronError] = useState("");

  const registeredJobs = useMemo(
    () => registry.filter((e) => e.registered),
    [registry],
  );

  const queueExtraQuery = useMemo(() => {
    const q = new URLSearchParams();
    q.set("tab", "queue");
    if (queueStatus) q.set("status", queueStatus);
    if (queueJobKey.trim()) q.set("job_key", queueJobKey.trim());
    if (queueQ.trim()) q.set("q", queueQ.trim());
    return q.toString();
  }, [queueStatus, queueJobKey, queueQ]);

  const loadSchedules = useCallback(async () => {
    setSchedulesLoading(true);
    setSchedulesError("");
    const sp = new URLSearchParams();
    if (schedulesQ.trim()) sp.set("q", schedulesQ.trim());
    try {
      const res = await fetch(`/api/admin/scheduler/schedules?${sp.toString()}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(await readApiError(res));
      setSchedules((await res.json()) as SchedulerScheduleRow[]);
    } catch (e) {
      setSchedulesError(e instanceof Error ? e.message : "스케줄 목록 조회 실패");
    } finally {
      setSchedulesLoading(false);
    }
  }, [schedulesQ]);

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
      const res = await fetch(`/api/admin/scheduler/queue?${sp.toString()}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(await readApiError(res));
      setQueueResult((await res.json()) as SchedulerQueuePage);
    } catch (e) {
      setQueueError(e instanceof Error ? e.message : "실행 이력 조회 실패");
    } finally {
      setQueueLoading(false);
    }
  }, [page, size, queueStatus, queueJobKey, queueQ]);

  useEffect(() => {
    if (tab === "schedules") void loadSchedules();
  }, [tab, loadSchedules]);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/admin/scheduler/registry", { cache: "no-store" });
        if (!res.ok) return;
        setRegistry((await res.json()) as RegistryEntry[]);
      } catch {
        /* ignore */
      }
    })();
  }, []);

  useEffect(() => {
    if (tab === "queue") void loadQueue();
  }, [tab, loadQueue]);

  useEffect(() => {
    if (!dialogOpen) {
      setCronPreview([]);
      setCronError("");
      return;
    }
    const expr = form.cron_expression.trim();
    if (!expr) {
      setCronPreview([]);
      setCronError("");
      return;
    }
    const handle = window.setTimeout(() => {
      void (async () => {
        try {
          const sp = new URLSearchParams({
            cron_expression: expr,
            count: "5",
          });
          const res = await fetch(`/api/admin/scheduler/cron-preview?${sp}`, {
            cache: "no-store",
          });
          if (!res.ok) {
            setCronPreview([]);
            setCronError(formatCronErrorMessage(await readApiError(res)));
            return;
          }
          const body = (await res.json()) as { next_runs: string[] };
          setCronPreview(body.next_runs ?? []);
          setCronError("");
        } catch {
          setCronPreview([]);
          setCronError("잘못된 Cron 표현식입니다.");
        }
      })();
    }, 300);
    return () => window.clearTimeout(handle);
  }, [dialogOpen, form.cron_expression]);

  const openCreate = () => {
    setDialogMode("create");
    setEditId(null);
    setForm(defaultScheduleForm(registeredJobs[0]?.job_key ?? ""));
    setDialogOpen(true);
  };

  const openEdit = (row: SchedulerScheduleRow) => {
    setDialogMode("edit");
    setEditId(row.id);
    setForm({
      job_key: row.job_key,
      name: row.name,
      cron_expression: row.cron_expression,
      enabled: row.enabled,
      description: row.description ?? "",
    });
    setDialogOpen(true);
  };

  const saveSchedule = async () => {
    if (cronError) {
      toast.error(cronError);
      return;
    }
    setBusy(true);
    try {
      const body = {
        name: form.name.trim(),
        enabled: form.enabled,
        cron_expression: form.cron_expression.trim(),
        description: form.description.trim() || null,
      };
      if (dialogMode === "create") {
        const res = await fetch("/api/admin/scheduler/schedules", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            job_key: form.job_key,
            ...body,
          }),
        });
        if (!res.ok) {
          const msg = await readApiError(res);
          throw new Error(
            /cron/i.test(msg) ? formatCronErrorMessage(msg) : msg,
          );
        }
        toast.success("스케줄이 등록되었습니다.");
      } else if (editId) {
        const res = await fetch(
          `/api/admin/scheduler/schedules/${encodeURIComponent(editId)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        );
        if (!res.ok) {
          const msg = await readApiError(res);
          throw new Error(
            /cron/i.test(msg) ? formatCronErrorMessage(msg) : msg,
          );
        }
        toast.success("스케줄이 수정되었습니다.");
      }
      setDialogOpen(false);
      await loadSchedules();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setBusy(true);
    try {
      const res = await fetch(
        `/api/admin/scheduler/schedules/${encodeURIComponent(deleteTarget.id)}`,
        { method: "DELETE" },
      );
      if (!res.ok && res.status !== 204) throw new Error(await readApiError(res));
      toast.success("스케줄이 삭제되었습니다.");
      setDeleteTarget(null);
      await loadSchedules();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setBusy(false);
    }
  };

  const enqueueRun = async (scheduleId: string) => {
    setBusy(true);
    try {
      const res = await fetch(
        `/api/admin/scheduler/schedules/${encodeURIComponent(scheduleId)}/enqueue-run`,
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
      const res = await fetch(`/api/admin/scheduler/queue/${row.id}/cancel`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await readApiError(res));
      toast.success("실행이 중지되었습니다.");
      await loadQueue();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "중지 실패");
    } finally {
      setBusy(false);
    }
  };

  const onSchedulesSearch = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const q = new URLSearchParams();
    q.set("tab", "schedules");
    const sq = String(fd.get("schedules_q") ?? "").trim();
    if (sq) q.set("schedules_q", sq);
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
    if (value === "schedules") {
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
          <TabsTrigger value="schedules">스케줄</TabsTrigger>
          <TabsTrigger value="queue">실행 이력</TabsTrigger>
        </TabsList>

        <TabsContent value="schedules" className="space-y-4">
          <section className="rounded-lg bg-card p-6 shadow-lg">
            <form onSubmit={onSchedulesSearch} className="mb-4 flex flex-wrap items-end gap-3">
              <Field className="w-[280px]">
                <FieldLabel htmlFor="schedules_q">검색 (이름·키)</FieldLabel>
                <Input
                  id="schedules_q"
                  name="schedules_q"
                  defaultValue={schedulesQ}
                  placeholder="name 또는 job_key"
                />
              </Field>
              <Button type="submit">검색</Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/admin/scheduler?tab=schedules")}
              >
                초기화
              </Button>
              <div className="flex-1" />
              <Button type="button" onClick={openCreate}>
                스케줄 등록
              </Button>
            </form>

            {schedulesError ? (
              <p className="text-sm text-destructive">{schedulesError}</p>
            ) : null}

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>이름</TableHead>
                  <TableHead>Job 키</TableHead>
                  <TableHead>활성</TableHead>
                  <TableHead>Cron</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedulesLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">
                      불러오는 중…
                    </TableCell>
                  </TableRow>
                ) : schedules.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">
                      등록된 스케줄이 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  schedules.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>
                        <span className="font-medium">{row.name}</span>
                        {!row.registered ? (
                          <span className="ml-2 inline-flex rounded bg-destructive/10 px-2 py-0.5 text-xs text-destructive">
                            고아
                          </span>
                        ) : null}
                      </TableCell>
                      <TableCell className="font-mono text-sm">{row.job_key}</TableCell>
                      <TableCell>{row.enabled ? "Y" : "N"}</TableCell>
                      <TableCell className="font-mono text-sm">{row.cron_expression}</TableCell>
                      <TableCell className="space-x-1 text-right">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={busy || !row.registered}
                          onClick={() => void enqueueRun(row.id)}
                        >
                          즉시 실행
                        </Button>
                        <Button type="button" size="sm" variant="secondary" onClick={() => openEdit(row)}>
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
          <section className="rounded-lg bg-card p-6 shadow-lg">
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
                <Button type="submit">검색</Button>
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
                  <TableHead>로그</TableHead>
                  <TableHead>오류</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queueLoading ? (
                  <TableRow>
                    <TableCell colSpan={10} className="text-center text-muted-foreground">
                      불러오는 중…
                    </TableCell>
                  </TableRow>
                ) : queueResult.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={10} className="text-center text-muted-foreground">
                      실행 이력이 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  queueResult.items.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell className="max-w-[120px] truncate font-mono text-xs">
                        {row.id}
                      </TableCell>
                      <TableCell className="font-mono text-sm">{row.job_key}</TableCell>
                      <TableCell>{row.action}</TableCell>
                      <TableCell>
                        <StatusBadge status={row.status} />
                      </TableCell>
                      <TableCell>{formatDateTimeInSeoul(row.created_at)}</TableCell>
                      <TableCell>{formatDateTimeInSeoul(row.started_at)}</TableCell>
                      <TableCell>{formatDateTimeInSeoul(row.finished_at)}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {row.related_log_id ? (
                          <span title={row.related_log_id}>{row.related_log_id.slice(0, 8)}…</span>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell
                        className="max-w-[200px] truncate text-xs"
                        title={row.error_message ?? ""}
                      >
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {dialogMode === "create" ? "스케줄 등록" : "스케줄 수정"}
            </DialogTitle>
          </DialogHeader>
          <FieldGroup>
            <FieldSet className="space-y-3">
              {dialogMode === "create" ? (
                <Field>
                  <FieldLabel>Job 키</FieldLabel>
                  <Select
                    value={form.job_key}
                    onValueChange={(v) => setForm((f) => ({ ...f, job_key: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {registeredJobs.map((e) => (
                        <SelectItem key={e.job_key} value={e.job_key}>
                          {e.title ? `${e.title} (${e.job_key})` : e.job_key}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              ) : (
                <Field>
                  <FieldLabel>Job 키</FieldLabel>
                  <Input value={form.job_key} disabled />
                </Field>
              )}
              <Field>
                <FieldLabel>이름</FieldLabel>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                />
              </Field>
              <Field orientation="horizontal">
                <Checkbox
                  id="schedule_enabled"
                  checked={form.enabled}
                  onCheckedChange={(checked) =>
                    setForm((f) => ({ ...f, enabled: checked === true }))
                  }
                />
                <FieldLabel htmlFor="schedule_enabled" className="font-normal">
                  활성 (cron 자동 실행)
                </FieldLabel>
              </Field>
              <Field>
                <FieldLabel>Cron 표현식</FieldLabel>
                <Input
                  className={`font-mono ${cronError ? "border-destructive" : ""}`}
                  value={form.cron_expression}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, cron_expression: e.target.value }))
                  }
                  placeholder="0 * * * * (매시 정각)"
                  aria-invalid={Boolean(cronError)}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  분 시 일 월 요일 — 예: <code>0 * * * *</code> 매시,{" "}
                  <code>*/10 * * * *</code> 10분마다
                </p>
                {cronError ? (
                  <p className="mt-1 text-sm text-destructive">{cronError}</p>
                ) : null}
                {!cronError && cronPreview.length > 0 ? (
                  <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
                    {cronPreview.map((t) => (
                      <li key={t}>다음: {formatDateTimeInSeoul(t)}</li>
                    ))}
                  </ul>
                ) : null}
              </Field>
              <Field>
                <FieldLabel>설명</FieldLabel>
                <Input
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                />
              </Field>
            </FieldSet>
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
              취소
            </Button>
            <Button
              type="button"
              disabled={
                busy ||
                !form.name.trim() ||
                !form.cron_expression.trim() ||
                Boolean(cronError)
              }
              onClick={() => void saveSchedule()}
            >
              저장
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteTarget !== null} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>스케줄 삭제</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            <span className="font-medium">{deleteTarget?.name}</span> (
            <span className="font-mono">{deleteTarget?.job_key}</span>) 을 삭제할까요?
          </p>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              취소
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={busy}
              onClick={() => void confirmDelete()}
            >
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
