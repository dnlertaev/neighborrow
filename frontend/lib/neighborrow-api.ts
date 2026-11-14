export type ResidentialComplex = { id: number; name: string };
export type User = { id: number; email: string; first_name: string; last_name: string; address: string; phone: string; social_url: string; residential_complex: ResidentialComplex | null; is_resident_verified: boolean };
export type Category = { id: number; name: string; slug: string };
export type Listing = {
  id: number; type: "offer" | "request"; title: string; description: string;
  category: number; category_name: string; owner: { id: number; display_name: string };
  condition: "good" | "like_new" | "any_working"; duration: string; needed_until: string | null;
  available: boolean; neighborhood: string; image_url: string; distance_km: number | null;
  created_at: string; updated_at: string; mine: boolean; has_responded: boolean;
};
export type Contacts = { owner: Listing["owner"]; phone: string; social_url: string };
export type Activity = { id: number; actor: Listing["owner"] | null; type: string; listing: number | null; item_title: string; description: string; created_at: string };
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
type Session = { access: string; refresh: string; user: User };
type RequestOptions = { method?: string; body?: unknown | (() => unknown); signal?: AbortSignal; authenticated?: boolean };

function errorMessage(data: unknown): string {
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(errorMessage).join(" ");
  if (data && typeof data === "object") return Object.entries(data).map(([key, value]) => `${["detail", "non_field_errors"].includes(key) ? "" : key.replaceAll("_", " ") + ": "}${errorMessage(value)}`).join("\n");
  return "The request could not be completed.";
}
export class ApiError extends Error {
  status: number;
  details: unknown;
  constructor(status: number, details: unknown) {
    super(errorMessage(details)); this.name = "ApiError"; this.status = status; this.details = details;
  }
}

// Tokens stay in this instance's memory. No passwords or JWTs are written to browser storage.
export class NeighborrowApi {
  private base: string;
  private transport: typeof fetch;
  private session: Session | null = null;
  private epoch = 0;
  private refreshTask: Promise<void> | null = null;
  private listeners = new Set<(user: User | null) => void>();
  constructor(base: string, transport: typeof fetch = globalThis.fetch.bind(globalThis)) {
    this.base = base.replace(/\/$/, ""); this.transport = transport;
  }
  subscribe(listener: (user: User | null) => void) {
    this.listeners.add(listener); listener(this.session?.user ?? null);
    return () => { this.listeners.delete(listener); };
  }
  private emit() { for (const listener of this.listeners) listener(this.session?.user ?? null); }
  clearSession() { this.epoch++; this.session = null; this.refreshTask = null; this.emit(); }
  private async decode(response: Response) {
    if (response.status === 204) return undefined;
    const text = await response.text();
    try { return text ? JSON.parse(text) : undefined; }
    catch { throw new ApiError(response.status, "The server returned an unexpected response. Please try again."); }
  }
  private async refresh() {
    if (this.refreshTask) return this.refreshTask;
    const current = this.session, epoch = this.epoch;
    if (!current) throw new ApiError(401, "Please sign in to continue.");
    const task = (async () => {
      const response = await this.transport(`${this.base}/auth/refresh`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: current.refresh }), credentials: "omit",
      });
      const data = await this.decode(response);
      if (epoch !== this.epoch) throw new DOMException("Session changed", "AbortError");
      if (!response.ok) {
        if (response.status === 401 || response.status === 400) this.clearSession();
        throw new ApiError(response.status, data);
      }
      this.session = { ...current, access: data.access, refresh: data.refresh };
    })();
    this.refreshTask = task;
    try { await task; } finally { if (this.refreshTask === task) this.refreshTask = null; }
  }
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    if (!path.startsWith("/") || path.startsWith("//") || /^[a-z]+:/i.test(path)) throw new Error("Use a relative API path");
    const epoch = this.epoch;
    const send = async () => {
      options.signal?.throwIfAborted();
      const headers: Record<string, string> = { Accept: "application/json" };
      if (options.authenticated !== false && this.session) headers.Authorization = `Bearer ${this.session.access}`;
      const body = typeof options.body === "function" ? options.body() : options.body;
      if (body !== undefined) headers["Content-Type"] = "application/json";
      return this.transport(`${this.base}${path}`, { method: options.method || "GET", headers,
        body: body === undefined ? undefined : JSON.stringify(body), signal: options.signal, credentials: "omit" });
    };
    let response = await send();
    if (epoch !== this.epoch) throw new DOMException("Session changed", "AbortError");
    if (response.status === 401 && options.authenticated !== false && this.session) {
      await this.refresh();
      if (epoch !== this.epoch) throw new DOMException("Session changed", "AbortError");
      response = await send();
    }
    const data = await this.decode(response);
    if (epoch !== this.epoch) throw new DOMException("Session changed", "AbortError");
    if (!response.ok) {
      if (response.status === 401 && options.authenticated !== false && this.session) this.clearSession();
      throw new ApiError(response.status, data || `Request failed (${response.status}).`);
    }
    return data as T;
  }
  async login(email: string, password: string) {
    const session = await this.request<Session>("/auth/login", { method: "POST", body: { email, password }, authenticated: false });
    this.epoch++; this.session = session; this.refreshTask = null; this.emit(); return session.user;
  }
  async register(data: { email: string; password: string; password_repeat: string; first_name: string; last_name: string }) {
    return this.request("/auth/register", { method: "POST", body: data, authenticated: false });
  }
  async verifyResidence(residential_complex: number, code: string) {
    const user = await this.request<User>("/auth/residential-complex/verify", {
      method: "POST", body: { residential_complex, code },
    });
    if (this.session) { this.session = { ...this.session, user }; this.emit(); }
    return user;
  }
  async updateProfile(data: Partial<Omit<User, "id" | "email">>) {
    const user = await this.request<User>("/auth/me", { method: "PATCH", body: data });
    if (this.session) { this.session = { ...this.session, user }; this.emit(); } return user;
  }
  async logout() {
    try { if (this.session) await this.request("/auth/logout", { method: "POST", body: () => ({ refresh: this.session?.refresh }) }); }
    finally { this.clearSession(); }
  }
  async changePassword(current_password: string, new_password: string, new_password_repeat: string) {
    await this.request("/auth/password/change", { method: "POST", body: { current_password, new_password, new_password_repeat } });
    this.clearSession();
  }
  async deleteAccount(current_password: string) {
    await this.request("/auth/me", { method: "DELETE", body: { current_password } }); this.clearSession();
  }
}
