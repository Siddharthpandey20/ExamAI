"use client"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Zap, Brain, RefreshCcw } from "lucide-react"

export type AIMode = "fast" | "reasoning"

interface AISettingsProps {
  mode: AIMode
  skipCache: boolean
  onModeChange: (mode: AIMode) => void
  onSkipCacheChange: (skip: boolean) => void
  compact?: boolean
}

export function AISettings({
  mode,
  skipCache,
  onModeChange,
  onSkipCacheChange,
  compact = false,
}: AISettingsProps) {
  if (compact) {
    return (
      <div className="flex items-center gap-3">
        <Select value={mode} onValueChange={(v) => onModeChange(v as AIMode)}>
          <SelectTrigger className="h-8 w-[130px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="fast">
              <span className="flex items-center gap-1.5">
                <Zap className="h-3 w-3 text-amber-500" />
                Fast
              </span>
            </SelectItem>
            <SelectItem value="reasoning">
              <span className="flex items-center gap-1.5">
                <Brain className="h-3 w-3 text-indigo-500" />
                Reasoning
              </span>
            </SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1.5">
          <Switch
            id="skip-cache-compact"
            checked={skipCache}
            onCheckedChange={onSkipCacheChange}
            className="h-4 w-7"
          />
          <Label htmlFor="skip-cache-compact" className="text-xs text-muted-foreground cursor-pointer">
            <RefreshCcw className="h-3 w-3" />
          </Label>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-muted/30 px-4 py-3">
      <div className="flex items-center gap-2">
        <Label className="text-sm font-medium text-foreground">Mode</Label>
        <Select value={mode} onValueChange={(v) => onModeChange(v as AIMode)}>
          <SelectTrigger className="h-9 w-[150px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="fast">
              <span className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-500" />
                Fast
              </span>
            </SelectItem>
            <SelectItem value="reasoning">
              <span className="flex items-center gap-2">
                <Brain className="h-4 w-4 text-indigo-500" />
                Reasoning
              </span>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center gap-2">
        <Switch
          id="skip-cache"
          checked={skipCache}
          onCheckedChange={onSkipCacheChange}
        />
        <Label htmlFor="skip-cache" className="text-sm text-muted-foreground cursor-pointer">
          Skip cache
        </Label>
      </div>
    </div>
  )
}
