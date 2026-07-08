"use client";

import * as Octicons from "@primer/octicons-react";
import type { ComponentType } from "react";

type OcticonCmp = ComponentType<{
  size?: number;
  className?: string;
  "aria-label"?: string;
}>;

export type ErIconName =
  | "dashboard"
  | "connectors"
  | "recorder"
  | "actions"
  | "executions"
  | "monitoring"
  | "publishing"
  | "playground"
  | "search"
  | "plus"
  | "check"
  | "checkCircle"
  | "x"
  | "xCircle"
  | "alert"
  | "bell"
  | "shield"
  | "shieldCheck"
  | "lock"
  | "key"
  | "gear"
  | "download"
  | "upload"
  | "link"
  | "globe"
  | "browser"
  | "server"
  | "database"
  | "cloud"
  | "code"
  | "terminal"
  | "copy"
  | "trash"
  | "filter"
  | "history"
  | "clock"
  | "calendar"
  | "chevronDown"
  | "chevronRight"
  | "chevronLeft"
  | "chevronUp"
  | "arrowRight"
  | "arrowDown"
  | "eye"
  | "bookmark"
  | "star"
  | "versions"
  | "telescope"
  | "goal"
  | "iterations"
  | "sync"
  | "beaker"
  | "package"
  | "briefcase"
  | "law"
  | "graph"
  | "robot"
  | "workflow"
  | "report"
  | "tasklist"
  | "inbox"
  | "dot"
  | "dotFill"
  | "circleSlash"
  | "bellFill"
  | "alertFill"
  | "checkCircleFill"
  | "xCircleFill"
  | "clockFill"
  | "stop"
  | "bug"
  | "lightbulb"
  | "person"
  | "signOut"
  | "diff"
  | "fileDiff"
  | "tools"
  | "meter"
  | "hubot"
  | "comment"
  | "sparkles"
  | "infinity"
  | "heart";

const MAP: Record<ErIconName, OcticonCmp> = {
  dashboard: Octicons.GraphIcon,
  connectors: Octicons.PlugIcon,
  recorder: Octicons.BroadcastIcon,
  actions: Octicons.CodespacesIcon,
  executions: Octicons.PlayIcon,
  monitoring: Octicons.PulseIcon,
  publishing: Octicons.RocketIcon,
  playground: Octicons.CopilotIcon,
  search: Octicons.SearchIcon,
  plus: Octicons.PlusIcon,
  check: Octicons.CheckIcon,
  checkCircle: Octicons.CheckCircleIcon,
  x: Octicons.XIcon,
  xCircle: Octicons.XCircleIcon,
  alert: Octicons.AlertIcon,
  bell: Octicons.BellIcon,
  shield: Octicons.ShieldIcon,
  shieldCheck: Octicons.ShieldCheckIcon,
  lock: Octicons.LockIcon,
  key: Octicons.KeyIcon,
  gear: Octicons.GearIcon,
  download: Octicons.DownloadIcon,
  upload: Octicons.UploadIcon,
  link: Octicons.LinkIcon,
  globe: Octicons.GlobeIcon,
  browser: Octicons.BrowserIcon,
  server: Octicons.ServerIcon,
  database: Octicons.DatabaseIcon,
  cloud: Octicons.CloudIcon,
  code: Octicons.CodeIcon,
  terminal: Octicons.TerminalIcon,
  copy: Octicons.CopyIcon,
  trash: Octicons.TrashIcon,
  filter: Octicons.FilterIcon,
  history: Octicons.HistoryIcon,
  clock: Octicons.ClockIcon,
  calendar: Octicons.CalendarIcon,
  chevronDown: Octicons.ChevronDownIcon,
  chevronRight: Octicons.ChevronRightIcon,
  chevronLeft: Octicons.ChevronLeftIcon,
  chevronUp: Octicons.ChevronUpIcon,
  arrowRight: Octicons.ArrowRightIcon,
  arrowDown: Octicons.ArrowDownIcon,
  eye: Octicons.EyeIcon,
  bookmark: Octicons.BookmarkIcon,
  star: Octicons.StarIcon,
  versions: Octicons.VersionsIcon,
  telescope: Octicons.TelescopeIcon,
  goal: Octicons.GoalIcon,
  iterations: Octicons.IterationsIcon,
  sync: Octicons.SyncIcon,
  beaker: Octicons.BeakerIcon,
  package: Octicons.PackageIcon,
  briefcase: Octicons.BriefcaseIcon,
  law: Octicons.LawIcon,
  graph: Octicons.GraphIcon,
  robot: Octicons.CopilotIcon,
  workflow: Octicons.WorkflowIcon,
  report: Octicons.ReportIcon,
  tasklist: Octicons.ChecklistIcon,
  inbox: Octicons.InboxIcon,
  dot: Octicons.DotIcon,
  dotFill: Octicons.DotFillIcon,
  circleSlash: Octicons.CircleSlashIcon,
  bellFill: Octicons.BellFillIcon,
  alertFill: Octicons.AlertFillIcon,
  checkCircleFill: Octicons.CheckCircleFillIcon,
  xCircleFill: Octicons.XCircleFillIcon,
  clockFill: Octicons.ClockFillIcon,
  stop: Octicons.StopIcon,
  bug: Octicons.BugIcon,
  lightbulb: Octicons.LightBulbIcon,
  person: Octicons.PersonIcon,
  signOut: Octicons.SignOutIcon,
  diff: Octicons.DiffIcon,
  fileDiff: Octicons.FileDiffIcon,
  tools: Octicons.ToolsIcon,
  meter: Octicons.MeterIcon,
  hubot: Octicons.HubotIcon,
  comment: Octicons.CommentIcon,
  sparkles: Octicons.StarIcon,
  infinity: Octicons.InfinityIcon,
  heart: Octicons.HeartIcon,
};

interface IconProps {
  name: ErIconName;
  size?: 16 | 20 | 24 | 32;
  className?: string;
  "aria-label"?: string;
}

export function Icon({ name, size = 20, className, ...rest }: IconProps) {
  const Cmp = MAP[name] ?? Octicons.QuestionIcon;
  return <Cmp size={size} className={className} {...rest} />;
}

export default Icon;
