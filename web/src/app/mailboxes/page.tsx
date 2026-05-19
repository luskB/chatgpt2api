"use client";

import { useEffect, useMemo, useState } from "react";
import type { ComponentProps } from "react";
import { CheckCircle2, CircleAlert, Clock3, LoaderCircle, Mail, RefreshCw, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  deleteImportedMailbox,
  fetchImportedMailboxes,
  importImportedMailboxes,
  resetImportedMailbox,
  type ImportedMailbox,
  type ImportedMailboxStatus,
  type ImportedMailboxSummary,
} from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

const emptySummary: ImportedMailboxSummary = { total: 0, unused: 0, leased: 0, used: 0, failed: 0 };

const statusMeta: Record<
  ImportedMailboxStatus,
  {
    label: string;
    badge: ComponentProps<typeof Badge>["variant"];
  }
> = {
  unused: { label: "未使用", badge: "success" },
  leased: { label: "占用中", badge: "warning" },
  used: { label: "已使用", badge: "secondary" },
  failed: { label: "失败", badge: "danger" },
};

const statusOptions: ImportedMailboxStatus[] = ["unused", "leased", "used", "failed"];

function formatTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function MailboxesPageContent() {
  const [items, setItems] = useState<ImportedMailbox[]>([]);
  const [summary, setSummary] = useState<ImportedMailboxSummary>(emptySummary);
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [text, setText] = useState("");
  const [fetchMethod, setFetchMethod] = useState<"imap" | "graph">("graph");
  const [imapHost, setImapHost] = useState("outlook.office365.com");
  const [imapPort, setImapPort] = useState("993");
  const [imapSsl, setImapSsl] = useState(true);
  const [imapFolder, setImapFolder] = useState("INBOX");
  const [graphTenant, setGraphTenant] = useState("consumers");
  const [graphClientId, setGraphClientId] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | ImportedMailboxStatus>("all");
  const [pageSize, setPageSize] = useState(20);
  const [customPageSize, setCustomPageSize] = useState("");
  const [page, setPage] = useState(1);

  const load = async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const data = await fetchImportedMailboxes();
      setItems(data.items);
      setSummary(data.summary);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载邮箱失败");
    } finally {
      if (!silent) setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const metrics = useMemo(
    () => [
      { key: "total", label: "邮箱总数", value: summary.total, icon: Mail, color: "text-stone-900" },
      { key: "unused", label: "未使用", value: summary.unused, icon: CheckCircle2, color: "text-emerald-600" },
      { key: "leased", label: "占用中", value: summary.leased, icon: Clock3, color: "text-amber-600" },
      { key: "used", label: "已使用", value: summary.used, icon: CheckCircle2, color: "text-stone-500" },
      { key: "failed", label: "失败", value: summary.failed, icon: CircleAlert, color: "text-rose-500" },
    ],
    [summary],
  );

  const filteredItems = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return items.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (!keyword) return true;
      return [item.email, item.id, item.client_id, item.graph_tenant, item.imap_host, item.last_error]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(keyword));
    });
  }, [items, query, statusFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageItems = filteredItems.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const pageStart = filteredItems.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const pageEnd = Math.min(currentPage * pageSize, filteredItems.length);

  useEffect(() => {
    setPage(1);
  }, [query, statusFilter, pageSize]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const applyCustomPageSize = () => {
    const value = Number(customPageSize);
    if (!Number.isFinite(value) || value <= 0) {
      toast.error("请输入有效的每页数量");
      return;
    }
    setPageSize(Math.min(500, Math.floor(value)));
  };

  const handleImport = async () => {
    if (!text.trim()) {
      toast.error("请先粘贴邮箱信息");
      return;
    }
    setIsImporting(true);
    try {
      const data = await importImportedMailboxes({
        text,
        fetch_method: fetchMethod,
        imap_host: imapHost,
        imap_port: Number(imapPort) || 993,
        imap_ssl: imapSsl,
        imap_folder: imapFolder,
        graph_tenant: graphTenant,
        graph_client_id: graphClientId,
      });
      setItems(data.items);
      setSummary(data.summary);
      if (data.errors.length > 0) {
        toast.warning(`导入 ${data.imported} 个，跳过 ${data.skipped} 个，失败 ${data.errors.length} 行`);
      } else {
        toast.success(`导入 ${data.imported} 个，跳过 ${data.skipped} 个`);
        setText("");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导入邮箱失败");
    } finally {
      setIsImporting(false);
    }
  };

  const handleReset = async (id: string) => {
    try {
      const data = await resetImportedMailbox(id);
      setItems(data.items);
      setSummary(data.summary);
      toast.success("邮箱已重置为未使用");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重置失败");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const data = await deleteImportedMailbox(id);
      setItems(data.items);
      setSummary(data.summary);
      toast.success("邮箱已删除");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除失败");
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-stone-950">邮箱管理</h1>
          <p className="mt-1 text-sm text-stone-500">先导入微软邮箱，再在注册机里选择“邮箱导入选项”使用。</p>
        </div>
        <Button variant="outline" className="h-10 rounded-xl border-stone-200 bg-white" onClick={() => void load(true)}>
          <RefreshCw className="size-4" />
          刷新
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-5">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card key={metric.key} className="bg-white/80">
              <CardContent className="flex items-center justify-between p-4">
                <div>
                  <p className="text-xs text-stone-500">{metric.label}</p>
                  <p className={`mt-1 text-2xl font-semibold ${metric.color}`}>{metric.value}</p>
                </div>
                <Icon className={`size-5 ${metric.color}`} />
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card className="bg-white/80">
        <CardHeader className="pb-4">
          <CardTitle>导入邮箱</CardTitle>
          <p className="text-sm text-stone-500">支持每行一个邮箱，Graph 推荐格式：email----password----client_id----refresh_token；IMAP 格式：email----password。</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="SaalxDdls8054+GByPgG@hotmail.com----password----client_id----refresh_token"
            className="min-h-36 rounded-xl border-stone-200 bg-white font-mono text-xs"
          />
          <div className="grid gap-4 md:grid-cols-4">
            <div className="space-y-2">
              <label className="text-sm text-stone-700">默认取码方式</label>
              <Select value={fetchMethod} onValueChange={(value) => setFetchMethod(value as "imap" | "graph")}>
                <SelectTrigger className="h-10 rounded-xl border-stone-200 bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="graph">Graph</SelectItem>
                  <SelectItem value="imap">IMAP</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {fetchMethod === "graph" ? (
              <>
                <div className="space-y-2">
                  <label className="text-sm text-stone-700">Graph Tenant</label>
                  <Input value={graphTenant} onChange={(event) => setGraphTenant(event.target.value)} placeholder="consumers" className="h-10 rounded-xl border-stone-200 bg-white" />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <label className="text-sm text-stone-700">默认 Client ID</label>
                  <Input value={graphClientId} onChange={(event) => setGraphClientId(event.target.value)} placeholder="可留空，---- 格式会使用每行的 client_id" className="h-10 rounded-xl border-stone-200 bg-white" />
                </div>
              </>
            ) : (
              <>
                <div className="space-y-2">
                  <label className="text-sm text-stone-700">IMAP Host</label>
                  <Input value={imapHost} onChange={(event) => setImapHost(event.target.value)} className="h-10 rounded-xl border-stone-200 bg-white" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-stone-700">IMAP Port</label>
                  <Input value={imapPort} onChange={(event) => setImapPort(event.target.value)} className="h-10 rounded-xl border-stone-200 bg-white" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm text-stone-700">Folder</label>
                  <Input value={imapFolder} onChange={(event) => setImapFolder(event.target.value)} className="h-10 rounded-xl border-stone-200 bg-white" />
                </div>
                <label className="flex items-center gap-3 pt-8 text-sm text-stone-700">
                  <Checkbox checked={imapSsl} onCheckedChange={(checked) => setImapSsl(Boolean(checked))} />
                  SSL
                </label>
              </>
            )}
          </div>
          <Button className="h-10 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800" onClick={() => void handleImport()} disabled={isImporting}>
            {isImporting ? <LoaderCircle className="size-4 animate-spin" /> : <Upload className="size-4" />}
            导入邮箱
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-white/80">
        <CardHeader className="space-y-3 pb-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <CardTitle>已导入邮箱</CardTitle>
            <div className="flex flex-col gap-2 md:flex-row md:items-center">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索邮箱、ID、Client 或错误"
                className="h-10 rounded-xl border-stone-200 bg-white md:w-64"
              />
              <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as "all" | ImportedMailboxStatus)}>
                <SelectTrigger className="h-10 rounded-xl border-stone-200 bg-white md:w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部状态</SelectItem>
                  {statusOptions.map((status) => (
                    <SelectItem key={status} value={status}>
                      {statusMeta[status].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={String(pageSize)} onValueChange={(value) => setPageSize(Number(value))}>
                <SelectTrigger className="h-10 rounded-xl border-stone-200 bg-white md:w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="20">20 / 页</SelectItem>
                  <SelectItem value="50">50 / 页</SelectItem>
                  <SelectItem value="100">100 / 页</SelectItem>
                </SelectContent>
              </Select>
              <div className="flex gap-2">
                <Input
                  value={customPageSize}
                  onChange={(event) => setCustomPageSize(event.target.value)}
                  placeholder="自定义"
                  className="h-10 w-24 rounded-xl border-stone-200 bg-white"
                />
                <Button variant="outline" className="h-10 rounded-xl border-stone-200 bg-white px-3" onClick={applyCustomPageSize}>
                  应用
                </Button>
              </div>
            </div>
          </div>
          <p className="text-xs text-stone-500">
            共 {items.length} 个，筛选后 {filteredItems.length} 个，当前显示 {pageStart}-{pageEnd}。
          </p>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>邮箱</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>方式</TableHead>
                <TableHead>凭据</TableHead>
                <TableHead>时间</TableHead>
                <TableHead>错误</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-10 text-center text-stone-400">
                    {items.length === 0 ? "暂无导入邮箱" : "没有符合筛选条件的邮箱"}
                  </TableCell>
                </TableRow>
              ) : (
                pageItems.map((item) => {
                  const meta = statusMeta[item.status] || statusMeta.unused;
                  return (
                    <TableRow key={item.id}>
                      <TableCell>
                        <div className="font-medium text-stone-900">{item.email}</div>
                        <div className="mt-1 text-xs text-stone-400">{item.id}</div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={meta.badge}>{meta.label}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="text-stone-700">{item.fetch_method === "graph" ? "Graph" : "IMAP"}</div>
                        <div className="mt-1 text-xs text-stone-400">
                          {item.fetch_method === "graph" ? item.graph_tenant : `${item.imap_host}:${item.imap_port}`}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="text-xs text-stone-500">密码：{item.password_masked || (item.has_password ? "已保存" : "-")}</div>
                        <div className="mt-1 text-xs text-stone-500">Token：{item.refresh_token_masked || (item.has_refresh_token ? "已保存" : "-")}</div>
                        {item.client_id ? <div className="mt-1 max-w-48 truncate text-xs text-stone-400">Client：{item.client_id}</div> : null}
                      </TableCell>
                      <TableCell>
                        <div className="text-xs text-stone-500">创建：{formatTime(item.created_at)}</div>
                        <div className="mt-1 text-xs text-stone-500">使用：{formatTime(item.used_at)}</div>
                        {item.leased_until ? <div className="mt-1 text-xs text-amber-600">占用到：{formatTime(item.leased_until)}</div> : null}
                      </TableCell>
                      <TableCell className="max-w-56 truncate text-xs text-rose-500">{item.last_error || "-"}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" className="h-8 rounded-lg border-stone-200 bg-white px-2" onClick={() => void handleReset(item.id)}>
                            重置
                          </Button>
                          <Button variant="ghost" className="h-8 rounded-lg px-2 text-rose-500 hover:bg-rose-50 hover:text-rose-600" onClick={() => void handleDelete(item.id)}>
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
          <div className="flex flex-col gap-3 border-t border-stone-100 px-4 py-3 text-sm text-stone-500 sm:flex-row sm:items-center sm:justify-between">
            <div>
              第 {currentPage} / {totalPages} 页，每页 {pageSize} 个
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                className="h-9 rounded-xl border-stone-200 bg-white px-3"
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                disabled={currentPage <= 1}
              >
                上一页
              </Button>
              <Button
                variant="outline"
                className="h-9 rounded-xl border-stone-200 bg-white px-3"
                onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                disabled={currentPage >= totalPages}
              >
                下一页
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function MailboxesPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);

  if (isCheckingAuth || !session || session.role !== "admin") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return <MailboxesPageContent />;
}
