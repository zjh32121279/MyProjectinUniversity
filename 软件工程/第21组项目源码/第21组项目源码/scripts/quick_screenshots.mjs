#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(SCRIPT_DIR, "..");

const DEFAULTS = {
  apiBase: "http://127.0.0.1:8000",
  adminBase: "http://127.0.0.1:5174",
  readerBase: "http://127.0.0.1:5175",
  superadminBase: "http://127.0.0.1:5176",
  viewport: "1536x864",
  waitMs: 2400,
};

const ROUTES = [
  {
    app: "admin",
    baseKey: "adminBase",
    login: "admin",
    routes: [
      // 登录
      ["login", "/login", "public"],
      // 首页
      ["home", "/admin/home", "admin"],
      // AI 工作台
      ["ai-workbench", "/admin/ai", "admin"],
      // 待处理中心
      ["tasks-all", "/admin/tasks", "admin"],
      ["tasks-high", "/admin/tasks", "admin", [{ type: "click", text: "高优先级" }]],
      ["tasks-borrow", "/admin/tasks", "admin", [{ type: "click", text: "借阅相关" }]],
      ["tasks-exception", "/admin/tasks", "admin", [{ type: "click", text: "异常处理" }]],
      ["tasks-other", "/admin/tasks", "admin", [{ type: "click", text: "其他" }]],
      // 馆藏管理
      ["catalog", "/admin/catalog", "admin"],
      ["catalog-detail", "/admin/catalog", "admin", [{ type: "click", text: "查看详情" }]],
      ["catalog-copies", "/admin/catalog", "admin", [
        { type: "click", text: "查看详情" },
        { type: "click", selector: '[role="dialog"] button:has-text("副本管理")' },
      ]],
      ["catalog-edit", "/admin/catalog", "admin", [
        { type: "click", text: "查看详情" },
        { type: "click", text: "编辑图书详情" },
      ]],
      ["catalog-add-copy", "/admin/catalog", "admin", [
        { type: "click", text: "查看详情" },
        { type: "click", selector: '[role="dialog"] button:has-text("副本管理")' },
        { type: "click", text: "新增副本" },
      ]],
      // 借阅与预约
      ["borrowing-home", "/admin/borrowing", "admin"],
      ["borrow-book", "/admin/borrowing/borrow", "admin"],
      ["return-book", "/admin/borrowing/return", "admin"],
      ["renew-book", "/admin/borrowing/renew", "admin"],
      ["reservation-records", "/admin/borrowing/reservation", "admin"],
      ["reservation-create", "/admin/borrowing/reservation", "admin", [{ type: "click", text: "新建预约" }]],
      // 读者管理
      ["readers", "/admin/readers", "admin"],
      // 通知中心
      ["notifications-all", "/admin/notifications", "admin"],
      ["notifications-system", "/admin/notifications", "admin", [{ type: "click", text: "系统通知" }]],
      ["notifications-due", "/admin/notifications", "admin", [{ type: "click", text: "到期提醒" }]],
      ["notifications-overdue", "/admin/notifications", "admin", [{ type: "click", text: "逾期提醒" }]],
      ["notifications-reservation", "/admin/notifications", "admin", [{ type: "click", text: "预约通知" }]],
      ["notifications-other", "/admin/notifications", "admin", [{ type: "click", text: "其他" }]],
      // 数据中心
      ["data-overview", "/admin/data", "admin"],
      ["data-collection", "/admin/data", "admin", [{ type: "click", text: "馆藏健康" }]],
      ["data-circulation", "/admin/data", "admin", [{ type: "click", text: "热门冷门" }]],
      ["data-readers", "/admin/data", "admin", [{ type: "click", text: "读者分析" }]],
      ["data-ai", "/admin/data", "admin", [{ type: "click", text: "AI 效率" }]],
      // 系统设置
      ["settings", "/admin/settings", "admin"],
    ],
  },
  {
    app: "reader",
    baseKey: "readerBase",
    login: "reader",
    routes: [
      ["login", "/login", "public"],
      ["register", "/register", "public"],
      ["forgot-password", "/forgot-password", "public"],
      ["home", "/home", "public"],
      ["search", "/search", "public"],
      ["search-query", "/search?query=%E7%8C%9C%E7%8C%9C", "public"],
      ["borrows", "/borrows", "reader"],
      ["reservations", "/reservations", "reader"],
      ["notifications", "/notifications", "reader"],
      ["profile", "/profile", "reader"],
    ],
  },
  {
    app: "superadmin",
    baseKey: "superadminBase",
    login: "superadmin",
    routes: [
      ["login", "/login", "public"],
      ["home", "/super-admin/home", "superadmin"],
      ["admins", "/super-admin/admins", "superadmin"],
      ["ai-rules", "/super-admin/ai-rules", "superadmin"],
      ["audit-security", "/super-admin/audit-security", "superadmin"],
    ],
  },
];

function parseArgs(argv) {
  const options = {
    apiBase: process.env.BOOKFLOW_API_BASE || DEFAULTS.apiBase,
    adminBase: process.env.BOOKFLOW_ADMIN_BASE || DEFAULTS.adminBase,
    readerBase: process.env.BOOKFLOW_READER_BASE || DEFAULTS.readerBase,
    superadminBase: process.env.BOOKFLOW_SUPERADMIN_BASE || DEFAULTS.superadminBase,
    adminAccount: process.env.BOOKFLOW_ADMIN_ACCOUNT || "A02-001",
    adminPassword: process.env.BOOKFLOW_ADMIN_PASSWORD || "BookFlow@123456",
    superadminAccount: process.env.BOOKFLOW_SUPERADMIN_ACCOUNT || "A01-001",
    superadminPassword: process.env.BOOKFLOW_SUPERADMIN_PASSWORD || "BookFlow@123456",
    readerAccount: process.env.BOOKFLOW_READER_ACCOUNT || "",
    readerPassword: process.env.BOOKFLOW_READER_PASSWORD || "",
    adminToken: process.env.BOOKFLOW_ADMIN_TOKEN || "",
    superadminToken: process.env.BOOKFLOW_SUPERADMIN_TOKEN || "",
    readerToken: process.env.BOOKFLOW_READER_TOKEN || "",
    outDir: "",
    viewport: DEFAULTS.viewport,
    waitMs: DEFAULTS.waitMs,
    fullPage: false,
    startDev: false,
    keepDev: false,
    readerStub: true,
    only: [],
    list: false,
    help: false,
  };

  for (const arg of argv) {
    if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--list") options.list = true;
    else if (arg === "--start-dev") options.startDev = true;
    else if (arg === "--full-page") options.fullPage = true;
    else if (arg === "--keep-dev") options.keepDev = true;
    else if (arg === "--no-reader-stub") options.readerStub = false;
    else if (arg.startsWith("--out=")) options.outDir = arg.slice("--out=".length);
    else if (arg.startsWith("--api-base=")) options.apiBase = arg.slice("--api-base=".length);
    else if (arg.startsWith("--admin-base=")) options.adminBase = arg.slice("--admin-base=".length);
    else if (arg.startsWith("--reader-base=")) options.readerBase = arg.slice("--reader-base=".length);
    else if (arg.startsWith("--superadmin-base=")) options.superadminBase = arg.slice("--superadmin-base=".length);
    else if (arg.startsWith("--viewport=")) options.viewport = arg.slice("--viewport=".length);
    else if (arg.startsWith("--wait-ms=")) options.waitMs = Number(arg.slice("--wait-ms=".length));
    else if (arg.startsWith("--only=")) options.only = arg.slice("--only=".length).split(",").map((item) => item.trim()).filter(Boolean);
    else throw new Error(`Unknown argument: ${arg}`);
  }

  if (!Number.isFinite(options.waitMs) || options.waitMs < 0) {
    throw new Error("--wait-ms must be a non-negative number");
  }
  return options;
}

function printHelp() {
  console.log(`Usage:
  node scripts/quick_screenshots.mjs [--start-dev] [--out=artifacts/screenshots/run] [--viewport=1536x864]

Captures all BookFlow UI routes from admin, reader, and superadmin apps.

Environment overrides:
  BOOKFLOW_API_BASE, BOOKFLOW_ADMIN_BASE, BOOKFLOW_READER_BASE, BOOKFLOW_SUPERADMIN_BASE
  BOOKFLOW_ADMIN_ACCOUNT, BOOKFLOW_ADMIN_PASSWORD
  BOOKFLOW_SUPERADMIN_ACCOUNT, BOOKFLOW_SUPERADMIN_PASSWORD
  BOOKFLOW_READER_ACCOUNT, BOOKFLOW_READER_PASSWORD
  BOOKFLOW_ADMIN_TOKEN, BOOKFLOW_SUPERADMIN_TOKEN, BOOKFLOW_READER_TOKEN

Options:
  --start-dev          Start missing local backend/frontends before capturing.
  --full-page          Capture full scrollable page instead of fixed viewport.
  --keep-dev           Keep processes started by --start-dev running.
  --no-reader-stub     Skip protected reader pages when no reader token/login is available.
  --only=a,b           Capture selected app/name pairs, route names, or app names.
  --list               Print the route capture plan and exit.
`);
}

function parseViewport(value) {
  const match = /^(\d+)x(\d+)$/i.exec(value);
  if (!match) throw new Error("--viewport must look like 1536x864");
  return { width: Number(match[1]), height: Number(match[2]) };
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function loadPlaywright() {
  const candidates = [
    path.join(ROOT_DIR, "package.json"),
    path.join(ROOT_DIR, "frontend", "user", "package.json"),
    path.join(ROOT_DIR, "frontend", "bookflow-admin", "package.json"),
    path.join(ROOT_DIR, "frontend", "bookflow_superadmin", "package.json"),
  ];
  for (const packageJson of candidates) {
    try {
      if (!fsSync.existsSync(packageJson)) continue;
      const requireFrom = createRequire(pathToFileURL(packageJson));
      return requireFrom("playwright");
    } catch {
      // Try the next frontend package.
    }
  }
  throw new Error("Playwright is not installed. Run npm install in one frontend package, then retry.");
}

async function fetchJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload?.success === false) {
    const message = payload?.error?.message || payload?.message || response.statusText;
    throw new Error(`${url} failed: ${message}`);
  }
  return payload.data ?? payload;
}

async function loginAdmin(apiBase, account, password) {
  const data = await fetchJson(`${apiBase}/auth/login`, { account, password });
  return data.access_token;
}

async function loginReader(apiBase, account, password) {
  const data = await fetchJson(`${apiBase}/reader-auth/login`, { account, password });
  const token = data.access_token;
  if (!token) throw new Error("API 返回缺少 access_token");
  const readerCode = data.reader?.reader_code;
  if (!readerCode) throw new Error("API 返回缺少 reader.reader_code");
  return {
    token,
    session: { reader_code: readerCode, name: data.reader?.name || "" },
  };
}

async function isReachable(url) {
  try {
    const response = await fetch(url, { method: "GET" });
    return response.ok || response.status < 500;
  } catch {
    return false;
  }
}

async function waitFor(url, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await isReachable(url)) return true;
    await new Promise((resolve) => setTimeout(resolve, 750));
  }
  return false;
}

function startProcess(command, args, cwd) {
  if (process.platform === "win32") {
    const quote = (part) => {
      const text = String(part);
      return /[\s&()^=;!'+,`~]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
    };
    const shellLine = [command, ...args].map(quote).join(" ");
    return spawn("cmd.exe", ["/d", "/c", shellLine], {
      cwd,
      windowsHide: true,
      detached: true,
      stdio: "ignore",
    });
  }
  const proc = spawn(command, args, {
    cwd,
    detached: true,
    stdio: "ignore",
    shell: false,
  });
  return proc;
}

function stopProcessTree(proc) {
  if (!proc?.pid) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(proc.pid), "/t", "/f"], {
      windowsHide: true,
      stdio: "ignore",
    });
  } else {
    try {
      process.kill(-proc.pid, "SIGTERM");
    } catch {
      proc.kill();
    }
  }
}


function killProcessOnPort(port) {
  if (process.platform === "win32") {
    const result = spawnSync("cmd.exe", ["/d", "/c", `for /f "tokens=5" %a in ('netstat -ano ^| findstr LISTENING ^| findstr :${port}') do @taskkill /F /PID %a`], {
      windowsHide: true,
      stdio: "ignore",
    });
    return result.status === 0 || result.status === 1;
  }

  spawnSync("bash", ["-lc", `for pid in $(lsof -ti:${port} 2>/dev/null || true); do kill -9 "$pid" 2>/dev/null || true; done`], {
    stdio: "ignore",
  });
  return true;
}

function maybeRestartDevPorts(options) {
  if (!options.startDev) return;
  const urls = [options.apiBase];
  if (needsApp(options, "admin")) urls.push(options.adminBase);
  if (needsApp(options, "reader")) urls.push(options.readerBase);
  if (needsApp(options, "superadmin")) urls.push(options.superadminBase);
  for (const raw of urls) {
    try {
      const port = Number(new URL(raw).port);
      if (Number.isFinite(port) && port > 0) killProcessOnPort(port);
    } catch {
      // Ignore invalid URLs.
    }
  }
}

async function ensureDevServers(options) {
  if (!options.startDev) return [];
  const started = [];
  const services = [
    {
      app: "api",
      url: `${options.apiBase}/health`,
      command: "python",
      args: ["-m", "uvicorn", "bookflow_core.main:app", "--host", "127.0.0.1", "--port", "8000"],
      cwd: path.join(ROOT_DIR, "backend"),
    },
    {
      app: "admin",
      url: options.adminBase,
      command: process.platform === "win32" ? "npm.cmd" : "npm",
      args: ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5174", "--strictPort"],
      cwd: path.join(ROOT_DIR, "frontend", "bookflow-admin"),
    },
    {
      app: "reader",
      url: options.readerBase,
      command: process.platform === "win32" ? "npm.cmd" : "npm",
      args: ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5175", "--strictPort"],
      cwd: path.join(ROOT_DIR, "frontend", "user"),
    },
    {
      app: "superadmin",
      url: options.superadminBase,
      command: process.platform === "win32" ? "npm.cmd" : "npm",
      args: ["run", "dev", "--", "--host", "127.0.0.1", "--port", "5176", "--strictPort"],
      cwd: path.join(ROOT_DIR, "frontend", "bookflow_superadmin"),
    },
  ];

  const neededServices = services.filter((service) => service.app === "api" || needsApp(options, service.app));

  for (const service of neededServices) {
    if (await isReachable(service.url)) continue;
    started.push(startProcess(service.command, service.args, service.cwd));
  }

  for (const service of neededServices) {
    const ok = await waitFor(service.url, 45000);
    if (!ok) throw new Error(`Service did not become reachable: ${service.url}`);
  }

  return started;
}


async function createLocalAdminToken(options, kind) {
  const wantSuper = kind === "superadmin";
  const pythonCode = String.raw`
import json
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from bookflow_core.core.security import create_access_token
want_super = sys.argv[1] == "1"
db_path = Path("data") / "bookflow.db"
con = sqlite3.connect(db_path)
cur = con.cursor()
row = cur.execute(
    """
    select id, admin_code, name, email, is_super_admin
    from admin_users
    where status = 'active' and is_super_admin = ?
    order by id
    limit 1
    """,
    (1 if want_super else 0,),
).fetchone()
if not row:
    raise SystemExit("no active admin account found")
role = "super_admin" if row[4] else "admin"
token = create_access_token(row[0], role=role, subject_type="admin", admin_code=row[1])
print(json.dumps({"token": token, "admin_code": row[1], "name": row[2], "email": row[3], "role": role}, ensure_ascii=False))
`;
  const result = spawnSync("python", ["-c", pythonCode, wantSuper ? "1" : "0"], {
    cwd: path.join(ROOT_DIR, "backend"),
    encoding: "utf8",
    windowsHide: true,
  });
  if (result.status !== 0) {
    const message = (result.stderr || result.stdout || "local token creation failed").trim();
    throw new Error(message);
  }
  return JSON.parse(result.stdout.trim());
}

async function createLocalReaderToken(options) {
  const pythonCode = String.raw`
import json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from bookflow_core.core.security import create_access_token
con = sqlite3.connect(str(Path("data") / "bookflow.db"))
cur = con.cursor()
row = cur.execute("select id, reader_code, name from reader_accounts where status = 'active' order by id limit 1").fetchone()
if not row:
    raise SystemExit("no active reader account found")
token = create_access_token(row[0], role="reader", subject_type="reader", reader_code=row[1])
print(json.dumps({"token": token, "session": {"reader_code": row[1], "name": row[2]}}, ensure_ascii=False))
`;
  const result = spawnSync("python", ["-c", pythonCode], {
    cwd: path.join(ROOT_DIR, "backend"),
    encoding: "utf8",
    windowsHide: true,
  });
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || "local reader token creation failed").trim());
  }
  return JSON.parse(result.stdout.trim());
}

async function buildAuthStorage(options) {
  const storage = {
    admin: null,
    superadmin: null,
    reader: null,
    readerStub: null,
  };

  const needsAll = !options.only.length;
  const needAdmin = needsAll || options.only.some((item) => item === "admin" || item.startsWith("admin/"));
  const needSuperadmin = needsAll || options.only.some((item) => item === "superadmin" || item.startsWith("superadmin/"));
  const needReader = needsAll || options.only.some((item) => item === "reader" || item.startsWith("reader/"));

  if (needAdmin) {
    if (options.adminToken) {
      storage.admin = { bookflow_admin_token: options.adminToken };
    } else {
      try {
        storage.admin = { bookflow_admin_token: await loginAdmin(options.apiBase, options.adminAccount, options.adminPassword) };
      } catch (error) {
        console.warn(`[WARN] 普通管理员密码登录失败，改用本地数据库令牌：${error.message}`);
        const local = await createLocalAdminToken(options, "admin");
        storage.admin = { bookflow_admin_token: local.token };
        console.warn(`[WARN] 已使用本地普通管理员账号：${local.admin_code} ${local.name || ""}`.trim());
      }
    }
  }

  if (needSuperadmin) {
    if (options.superadminToken) {
      storage.superadmin = { bookflow_admin_token: options.superadminToken };
    } else {
      try {
        storage.superadmin = { bookflow_admin_token: await loginAdmin(options.apiBase, options.superadminAccount, options.superadminPassword) };
      } catch (error) {
        console.warn(`[WARN] 超级管理员密码登录失败，改用本地数据库令牌：${error.message}`);
        const local = await createLocalAdminToken(options, "superadmin");
        storage.superadmin = { bookflow_admin_token: local.token };
        console.warn(`[WARN] 已使用本地超级管理员账号：${local.admin_code} ${local.name || ""}`.trim());
      }
    }
  }

  if (needReader) {
    if (options.readerToken) {
      storage.reader = {
        bookflow_user_token: options.readerToken,
        bookflow_user_session: JSON.stringify({ reader_code: "SCREENSHOT", name: "Screenshot Reader" }),
      };
    } else if (options.readerAccount && options.readerPassword) {
      try {
        const reader = await loginReader(options.apiBase, options.readerAccount, options.readerPassword);
        storage.reader = {
          bookflow_user_token: reader.token,
          bookflow_user_session: JSON.stringify(reader.session),
        };
      } catch (error) {
        console.warn(`[WARN] 读者登录失败，将使用 reader stub：${error.message}`);
      }
    }

    if (!storage.reader && options.readerStub) {
      try {
        const local = await createLocalReaderToken(options);
        storage.readerStub = {
          bookflow_user_token: local.token,
          bookflow_user_session: JSON.stringify(local.session),
        };
      } catch {
        storage.readerStub = {
          bookflow_user_session: JSON.stringify({ reader_code: "SCREENSHOT", name: "Screenshot Reader" }),
        };
      }
    }
  }

  return storage;
}

function storageForAuth(auth, storage) {
  if (auth === "admin") return storage.admin;
  if (auth === "superadmin") return storage.superadmin;
  if (auth === "reader") return storage.reader || storage.readerStub;
  return null;
}

function normalizeRoute(route) {
  return {
    name: route[0],
    routePath: route[1],
    auth: route[2],
    actions: route[3] || [],
  };
}

function shouldCaptureRoute(app, normalized, options) {
  if (!options.only.length) return true;
  const id = `${app.app}/${normalized.name}`;
  return options.only.some((item) => item === app.app || item === normalized.name || item === id);
}

function needsApp(options, appName) {
  if (!options.only.length) return true;
  return options.only.some((item) => item === appName || item.startsWith(`${appName}/`));
}

async function clickByText(page, text) {
  const button = page.getByRole("button", { name: text, exact: true });
  if ((await button.count()) > 0) {
    await button.first().click();
    return;
  }
  const link = page.getByRole("link", { name: text, exact: true });
  if ((await link.count()) > 0) {
    await link.first().click();
    return;
  }
  const textLocator = page.getByText(text, { exact: true });
  if ((await textLocator.count()) > 0) {
    await textLocator.first().click();
    return;
  }
  throw new Error(`Cannot find clickable text: ${text}`);
}

async function runRouteActions(page, actions, waitMs) {
  for (const action of actions) {
    if (action.type === "click") {
      if (action.selector) {
        await page.locator(action.selector).first().click();
      } else {
        await clickByText(page, action.text);
      }
    } else if (action.type === "select") {
      await page.locator(action.selector).selectOption(action.value);
    } else {
      throw new Error(`Unknown route action type: ${action.type}`);
    }
    await waitForPageSettled(page, waitMs);
  }
}

async function waitForPageSettled(page, waitMs, intendedPath = "") {
  const timeout = Math.max(6000, waitMs * 3);
  await page.waitForLoadState("networkidle", { timeout }).catch(() => undefined);
  await page.waitForFunction(
    () => {
      const root = document.querySelector("#root");
      const hasText = Boolean(root?.textContent?.trim() && root.textContent.trim().length > 20);
      const busy = document.querySelector('[aria-busy="true"]');
      const skeleton = document.querySelector('.animate-pulse, .skeleton, .skeleton-block, [class*="Skeleton"], [class*="skeleton"]');
      return hasText && !busy && !skeleton;
    },
    undefined,
    { timeout },
  ).catch(() => undefined);

  // Wait an extra beat then check for error / redirect states.
  await page.waitForTimeout(Math.min(waitMs, 1200));

  if (intendedPath === "/login") return;

  const isError = await page.evaluate(() => {
    const onLogin = window.location.pathname === "/login";
    const bodyText = document.body.innerText || "";
    const errorHint = bodyText.includes("加载失败") || bodyText.includes("数据暂不可用") || bodyText.includes("服务暂不可用");
    return onLogin || errorHint;
  }).catch(() => false);

  if (isError) {
    const currentUrl = page.url();
    const onLogin = currentUrl.includes("/login");
    if (onLogin) {
      console.warn(`[WARN] 已重定向到 /login（auth token 无效或过期）— ${currentUrl}`);
    } else {
      console.warn(`[WARN] 页面显示错误提示，等待 react-query 重试恢复 — ${currentUrl}`);
      // Wait for error state to resolve (react-query retries), or timeout.
      await page.waitForFunction(
        () => {
          const bodyText = document.body.innerText || "";
          const stillError = bodyText.includes("加载失败") || bodyText.includes("数据暂不可用") || bodyText.includes("服务暂不可用");
          return !stillError;
        },
        { timeout: 12000 },
      ).catch(() => console.warn(`[WARN] 错误状态在 12s 内未恢复，截图可能为错误页 — ${currentUrl}`));
      // Extra settle time after recovery.
      await page.waitForTimeout(Math.min(waitMs, 900));
    }
  }
}

function withTimeout(promise, timeoutMs, label) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

async function captureRoute(browser, options, app, route, storage, index, outDir) {
  const { name, routePath, auth, actions } = normalizeRoute(route);
  const baseUrl = options[app.baseKey];
  const url = `${baseUrl}${routePath}`;
  const routeStorage = storageForAuth(auth, storage);
  const fileName = `${String(index).padStart(2, "0")}-${app.app}-${name}.png`;
  const filePath = path.join(outDir, fileName);

  if (auth !== "public" && !routeStorage) {
    return {
      app: app.app,
      name,
      path: routePath,
      skipped: true,
      reason: `Missing ${auth} auth storage`,
    };
  }

  const context = await browser.newContext({ viewport: parseViewport(options.viewport), deviceScaleFactor: 1 });
  if (routeStorage) {
    await context.addInitScript((items) => {
      for (const [key, value] of Object.entries(items)) {
        window.localStorage.setItem(key, String(value));
      }
    }, routeStorage);
  }
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") pageErrors.push(message.text());
  });

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await waitForPageSettled(page, options.waitMs, routePath);
    await runRouteActions(page, actions, options.waitMs);
    await page.screenshot({ path: filePath, fullPage: options.fullPage });
    const title = await page.title().catch(() => "");
    const finalUrl = page.url();
    return {
      app: app.app,
      name,
      path: routePath,
      auth,
      url,
      finalUrl,
      title,
      actions,
      file: path.relative(ROOT_DIR, filePath),
      errors: pageErrors.slice(0, 8),
    };
  } finally {
    await context.close().catch(() => undefined);
  }
}

function printRouteList() {
  let index = 1;
  for (const app of ROUTES) {
    for (const route of app.routes) {
      const { name, routePath, auth, actions } = normalizeRoute(route);
      const actionText = actions.length ? ` actions=${actions.map((action) => action.selector || action.text || action.value || action.type).join(",")}` : "";
      console.log(`${String(index).padStart(2, "0")} ${app.app.padEnd(10)} ${auth.padEnd(10)} ${name.padEnd(30)} ${routePath}${actionText}`);
      index += 1;
    }
  }
}

function localChromiumExecutable() {
  const candidates = process.platform === "win32"
    ? [
        process.env.CHROME_PATH,
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
      ]
    : [process.env.CHROME_PATH, "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"];
  return candidates.filter(Boolean).find((candidate) => fsSync.existsSync(candidate));
}

async function launchChromium(chromium) {
  try {
    return await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  } catch (error) {
    const executablePath = localChromiumExecutable();
    if (!executablePath) throw error;
    console.warn(`[WARN] Playwright bundled browser unavailable, using system browser: ${executablePath}`);
    return await chromium.launch({ headless: true, executablePath, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }
  if (options.list) {
    printRouteList();
    return;
  }

  const outDir = path.resolve(ROOT_DIR, options.outDir || path.join("artifacts", "screenshots", timestamp()));
  const screenshotsRoot = path.resolve(ROOT_DIR, "artifacts", "screenshots");
  const relativeOut = path.relative(screenshotsRoot, outDir);
  if (relativeOut.startsWith("..") || path.isAbsolute(relativeOut)) {
    throw new Error(`Refusing to clean output directory outside artifacts/screenshots: ${outDir}`);
  }
  await fs.rm(outDir, { recursive: true, force: true });
  await fs.mkdir(outDir, { recursive: true });

  maybeRestartDevPorts(options);
  const started = await ensureDevServers(options);
  const { chromium } = loadPlaywright();
  let browser = await launchChromium(chromium);
  const manifest = {
    createdAt: new Date().toISOString(),
    viewport: options.viewport,
    fullPage: options.fullPage,
    outputDir: path.relative(ROOT_DIR, outDir),
    routes: [],
  };

  try {
    const storage = await buildAuthStorage(options);
    const capturePlan = [];
    let routeIndex = 1;
    for (const app of ROUTES) {
      for (const route of app.routes) {
        const normalized = normalizeRoute(route);
        capturePlan.push({ index: routeIndex, app, route, normalized });
        routeIndex += 1;
      }
    }

    for (const item of capturePlan) {
      if (!shouldCaptureRoute(item.app, item.normalized, options)) continue;
      let result = await withTimeout(
        captureRoute(browser, options, item.app, item.route, storage, item.index, outDir),
        Math.max(20000, options.waitMs * 8),
        `${item.app.app}/${item.normalized.name}`,
      ).catch(async (error) => {
        const message = error.message || String(error);
        if (message.includes("Target page, context or browser has been closed") || message.includes("Browser has been closed") || message.includes("timed out after")) {
          console.warn(`[WARN] 浏览器进程中断，重启后重试：${item.app.app}/${item.normalized.name}`);
          await browser.close().catch(() => undefined);
          browser = await launchChromium(chromium);
          return withTimeout(
            captureRoute(browser, options, item.app, item.route, storage, item.index, outDir),
            Math.max(20000, options.waitMs * 8),
            `${item.app.app}/${item.normalized.name} retry`,
          ).catch((retryError) => ({
            index: item.index,
            app: item.app.app,
            name: item.normalized.name,
            path: item.normalized.routePath,
            auth: item.normalized.auth,
            actions: item.normalized.actions,
            failed: true,
            error: retryError.message,
          }));
        }
        return {
          index: item.index,
          app: item.app.app,
          name: item.normalized.name,
          path: item.normalized.routePath,
          auth: item.normalized.auth,
          actions: item.normalized.actions,
          failed: true,
          error: message,
        };
      });
      manifest.routes.push(result);
      console.log(`${String(item.index).padStart(2, "0")} ${result.skipped ? "SKIP" : result.failed ? "FAIL" : "OK  "} ${item.app.app}/${item.normalized.name}`);
    }
  } finally {
    await browser.close().catch(() => undefined);
    if (!options.keepDev) {
      for (const proc of started) stopProcessTree(proc);
    }
  }

  await fs.writeFile(path.join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2), "utf8");
  const okCount = manifest.routes.filter((item) => !item.failed && !item.skipped).length;
  const failedCount = manifest.routes.filter((item) => item.failed).length;
  const skippedCount = manifest.routes.filter((item) => item.skipped).length;
  console.log(`Done. screenshots=${okCount} failed=${failedCount} skipped=${skippedCount} out=${path.relative(ROOT_DIR, outDir)}`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
