"use client";

import { useEffect, useRef, useState } from "react";
import { Copy, KeyRound, LoaderCircle, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { createMcpKey, deleteMcpKey, fetchMcpKeys, type McpKey } from "@/lib/api";

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function McpKeysCard() {
  const didLoadRef = useRef(false);
  const [items, setItems] = useState<McpKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [revealedKey, setRevealedKey] = useState("");
  const [deletingItem, setDeletingItem] = useState<McpKey | null>(null);
  const [pendingId, setPendingId] = useState("");

  const load = async () => {
    setIsLoading(true);
    try {
      const data = await fetchMcpKeys();
      setItems(data.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载 MCP Key 失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (didLoadRef.current) return;
    didLoadRef.current = true;
    void load();
  }, []);

  const handleCopy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success("已复制到剪贴板");
    } catch {
      toast.error("复制失败，请手动复制");
    }
  };

  const handleCreate = async () => {
    setIsCreating(true);
    try {
      const data = await createMcpKey(name.trim());
      setItems(data.items);
      setRevealedKey(data.key);
      setName("");
      setIsDialogOpen(false);
      toast.success("MCP Key 已创建");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建 MCP Key 失败");
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!deletingItem) return;
    const item = deletingItem;
    setPendingId(item.id);
    try {
      const data = await deleteMcpKey(item.id);
      setItems(data.items);
      setDeletingItem(null);
      toast.success("MCP Key 已删除");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除 MCP Key 失败");
    } finally {
      setPendingId("");
    }
  };

  return (
    <>
      <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="space-y-6 p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl bg-emerald-50">
                <KeyRound className="size-5 text-emerald-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold tracking-tight">MCP API Key</h2>
                <p className="text-sm text-stone-500">
                  创建只允许连接 MCP 搜索接口的专属密钥，不授予后台管理权限。
                </p>
              </div>
            </div>
            <Button className="h-9 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800" onClick={() => setIsDialogOpen(true)}>
              <Plus className="size-4" />
              新增 MCP Key
            </Button>
          </div>

          {revealedKey ? (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-900">
              <div className="font-medium">新 MCP Key 仅展示一次，请立即保存：</div>
              <div className="mt-3 flex flex-col gap-3 rounded-lg border border-emerald-200 bg-white/80 p-3 md:flex-row md:items-center md:justify-between">
                <code className="break-all font-mono text-[13px]">{revealedKey}</code>
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 rounded-xl border-emerald-200 bg-white px-4 text-emerald-700"
                  onClick={() => void handleCopy(revealedKey)}
                >
                  <Copy className="size-4" />
                  复制
                </Button>
              </div>
            </div>
          ) : null}

          {isLoading ? (
            <div className="flex items-center justify-center py-10">
              <LoaderCircle className="size-5 animate-spin text-stone-400" />
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-xl bg-stone-50 px-6 py-10 text-center text-sm text-stone-500">
              暂无 MCP 专属 Key。创建后可用于 /mcp?ApiKey=... 连接 Cherry、Chatbox 等客户端。
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item) => {
                const isPending = pendingId === item.id;
                return (
                  <div key={item.id} className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white px-4 py-4 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="truncate text-sm font-medium text-stone-800">{item.name}</div>
                        <Badge variant="success" className="rounded-md">MCP</Badge>
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-500">
                        <span>创建时间 {formatDateTime(item.created_at)}</span>
                        <span>最近使用 {formatDateTime(item.last_used_at)}</span>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      className="h-9 rounded-xl border-rose-200 bg-white px-4 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                      onClick={() => setDeletingItem(item)}
                      disabled={isPending}
                    >
                      {isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                      删除
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="rounded-2xl p-6">
          <DialogHeader className="gap-2">
            <DialogTitle>新增 MCP Key</DialogTitle>
            <DialogDescription className="text-sm leading-6">
              可选填写名称用于区分客户端。创建后系统只保存哈希，明文 Key 只展示一次。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">名称</label>
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：Cherry、Chatbox、Claude Desktop"
              className="h-11 rounded-xl border-stone-200 bg-white"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200" onClick={() => setIsDialogOpen(false)} disabled={isCreating}>
              取消
            </Button>
            <Button type="button" className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800" onClick={() => void handleCreate()} disabled={isCreating}>
              {isCreating ? <LoaderCircle className="size-4 animate-spin" /> : <Plus className="size-4" />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(deletingItem)} onOpenChange={(open) => (!open ? setDeletingItem(null) : null)}>
        <DialogContent className="rounded-2xl p-6">
          <DialogHeader className="gap-2">
            <DialogTitle>删除 MCP Key</DialogTitle>
            <DialogDescription className="text-sm leading-6">
              确认删除 MCP Key「{deletingItem?.name}」吗？删除后对应客户端将无法继续连接 MCP。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="secondary" className="h-10 rounded-xl bg-stone-100 px-5 text-stone-700 hover:bg-stone-200" onClick={() => setDeletingItem(null)} disabled={Boolean(pendingId)}>
              取消
            </Button>
            <Button type="button" className="h-10 rounded-xl bg-rose-600 px-5 text-white hover:bg-rose-700" onClick={() => void handleDelete()} disabled={Boolean(pendingId)}>
              {pendingId ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
