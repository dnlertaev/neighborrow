"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel } from "@/components/ui/alert-dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from "@/components/ui/table";
import { Pagination, PaginationContent, PaginationItem } from "@/components/ui/pagination";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { ApiError, NeighborrowApi, type User, type ResidentialComplex, type Category, type Listing, type Contacts, type Activity, type Page } from "@/lib/neighborrow-api";

const api = new NeighborrowApi(process.env.NEXT_PUBLIC_NEIGHBORROW_API_URL || "http://127.0.0.1:8000/api/v1");
const phonePattern = "\\+7[0-9]{10}";
const conditions = { good: "Good", like_new: "Like new", any_working: "Any working" };
const activityLabels: Record<string, string> = { offer_created: "Offer created", request_created: "Request created", listing_updated: "Listing updated", listing_deleted: "Listing deleted", offer_requested: "Offer requested", request_response: "Request response" };
type Resource<T> = { data: T | null; error: string; loading: boolean; resourceKey: string | null };
function message(error: unknown) { return error instanceof ApiError ? error.message : "Cannot reach the server. Please check your connection and try again."; }
function qs(values: Record<string, string | number | boolean | undefined>) { return new URLSearchParams(Object.entries(values).filter(([, value]) => value !== undefined).map(([key, value]) => [key, String(value)])).toString(); }
function useResource<T>(path: string | null, revision: number): Resource<T> {
  const [state, setState] = useState<Resource<T>>({ data: null, error: "", loading: false, resourceKey: null });
  const resourceKey = path ? `${path}:${revision}` : null;
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api.request<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setState({ data, error: "", loading: false, resourceKey });
    }).catch(error => { if (!controller.signal.aborted && error?.name !== "AbortError") setState({ data: null, error: message(error), loading: false, resourceKey }); });
    return () => controller.abort();
  }, [path, revision, resourceKey]);
  return state.resourceKey === resourceKey ? state : { data: null, error: "", loading: !!path, resourceKey };
}
function Picker({ value, onChange, options, label }: { value: string; onChange: (s: string) => void; options: { value: string; label: string }[]; label: string }) {
  return <Select value={value} onValueChange={onChange}><SelectTrigger aria-label={label}><SelectValue placeholder={`Select ${label.toLowerCase()}`} /></SelectTrigger><SelectContent>{options.map(x => <SelectItem value={x.value} key={x.value}>{x.label}</SelectItem>)}</SelectContent></Select>;
}
function SearchBox({ value, onChange, onSubmit, className = "" }: { value: string; onChange: (s: string) => void; onSubmit: () => void; className?: string }) {
  return <form className={`search-box ${className}`} onSubmit={e => { e.preventDefault(); onSubmit(); }}><input aria-label="Search for items" placeholder="Search for items..." maxLength={200} value={value} onChange={e => onChange(e.target.value)} />{value && <button type="button" aria-label="Clear search" onClick={() => onChange("")}>×</button>}</form>;
}
function LoadState({ loading, error, retry }: { loading: boolean; error: string; retry: () => void }) {
  if (error) return <div className="request-error" role="alert"><p>{error}</p><Button variant="outline" onClick={retry}>Try again</Button></div>;
  if (loading) return <div className="loading-state" role="status" aria-label="Loading"><Skeleton className="h-6 w-48" /><Skeleton className="h-24 w-full" /><span className="sr-only">Loading…</span></div>;
  return null;
}
function Pager({ data, page, onChange }: { data: Page<unknown> | null; page: number; onChange: (n: number) => void }) {
  if (!data || (!data.previous && !data.next)) return null;
  return <Pagination><PaginationContent><PaginationItem><Button variant="outline" disabled={!data.previous} onClick={() => onChange(page - 1)}>Previous</Button></PaginationItem><PaginationItem><span className="page-number" aria-live="polite">Page {page} · {data.count} results</span></PaginationItem><PaginationItem><Button variant="outline" disabled={!data.next} onClick={() => onChange(page + 1)}>Next</Button></PaginationItem></PaginationContent></Pagination>;
}
function safeLink(url: string) { try { const parsed = new URL(url); return ["https:", "http:"].includes(parsed.protocol) ? parsed.href : null; } catch { return null; } }
function ListingPhoto({ url, title }: { url: string; title: string }) {
  const validUrl = safeLink(url);
  return <>
    {validUrl && (
      // Listing photos are user-provided URLs, so Next image optimization is unavailable here.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={validUrl} alt={title} referrerPolicy="no-referrer" onError={event => { event.currentTarget.hidden = true; const fallback = event.currentTarget.nextElementSibling as HTMLElement | null; if (fallback) fallback.hidden = false; }} />
    )}
    <div className="no-photo" hidden={!!validUrl}>No photo available</div>
  </>;
}
function dateLabel(date: string) { return new Date(date).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
function deadlineLabel(date: string) { return new Date(`${date}T12:00:00`).toLocaleDateString(); }
function isAvailable(item: Listing) { return item.available && (!item.needed_until || item.needed_until >= new Date().toISOString().slice(0, 10)); }
function Card({ item, onOpen }: { item: Listing; onOpen: (id: number) => void }) {
  return <article className="item-card"><div className="card-meta"><span>{item.type === "offer" ? "Offer" : "Request"}</span><span>{item.mine ? "Your listing" : item.neighborhood || "Neighborhood not specified"}</span></div><button className="card-title" onClick={() => onOpen(item.id)}>{item.title}</button><p>{item.description}</p><div className="card-condition">{item.type === "offer" ? `Condition: ${conditions[item.condition]}` : `Needed: ${item.duration}`}</div><div className="card-user"><span className="user"><span className="avatar small" />{item.owner.display_name}</span>{item.type === "offer" && <strong className={isAvailable(item) ? "success" : "danger"}>{isAvailable(item) ? "Available" : "Unavailable"}</strong>}</div><Button variant={isAvailable(item) ? "default" : "secondary"} onClick={() => onOpen(item.id)}>{!isAvailable(item) ? "View item" : item.type === "offer" ? "Request" : "Offer help"}</Button></article>;
}

export default function Home() {
  const [route, setRoute] = useState("home"), [user, setUser] = useState<User | null>(null), [revision, setRevision] = useState(0);
  const [query, setQuery] = useState(""), [search, setSearch] = useState(""), [type, setType] = useState("all"), [category, setCategory] = useState("all"), [ordering, setOrdering] = useState("newest");
  const [available, setAvailable] = useState(false), [filters, setFilters] = useState(false);
  const [page, setPage] = useState(1), [activityPage, setActivityPage] = useState(1), [matchPage, setMatchPage] = useState(1), [modal, setModal] = useState("");
  const [hidden, setHidden] = useState(false), [busy, setBusy] = useState(false), [formError, setFormError] = useState("");
  const [createCategory, setCreateCategory] = useState(""), [condition, setCondition] = useState("");
  const [residentialComplexId, setResidentialComplexId] = useState("");
  const busyRef = useRef(false);
  const [returnTo, setReturnTo] = useState("dashboard");
  const view = route.split("/")[0], idText = route.split("/")[1], itemId = /^\d+$/.test(idText || "") && Number(idText) > 0 ? Number(idText) : null;
  const dashboard = ["dashboard", "activity"].includes(view) || (view === "home" && !!user);
  const protectedPage = ["dashboard", "activity", "profile", "profile-edit", "listings", "create", "edit", "explore", "detail", "verify", "change-residence"].includes(view);
  const needsResidence = !!user && !user.is_resident_verified && !["profile", "profile-edit"].includes(view);
  const changingResidence = view === "change-residence" && !!user?.is_resident_verified;
  const editing = view === "edit", creating = view === "create", createType = route === "create/offer" ? "offer" : "request";
  const invalidate = () => setRevision(n => n + 1);
  const navigate = (path: string) => { setFormError(""); setModal(""); setRoute(path); setPage(1); window.history.pushState(null, "", `#${path}`); window.scrollTo({ top: 0 }); };
  const signInFor = (target: string) => { setReturnTo(target); navigate("signin"); };
  const openItem = (id: number) => { setMatchPage(1); navigate(`detail/${id}`); };
  const startCreate = (kind: "offer" | "request") => { setCreateCategory(""); setCondition("good"); if (!user) signInFor(`create/${kind}`); else navigate(user.is_resident_verified ? `create/${kind}` : "verify"); };
  const searchNow = () => { setSearch(query.trim()); setPage(1); if (!user) signInFor("explore"); else navigate(user.is_resident_verified ? "explore" : "verify"); };
  useEffect(() => { const sync = () => { setRoute(window.location.hash.slice(1) || "home"); setFormError(""); setModal(""); setPage(1); }; sync(); window.addEventListener("hashchange", sync); window.addEventListener("popstate", sync); return () => { window.removeEventListener("hashchange", sync); window.removeEventListener("popstate", sync); }; }, []);
  useEffect(() => api.subscribe(current => { setUser(current); setRevision(n => n + 1); setPage(1); if (!current) setModal(""); }), []);
  useEffect(() => { const timer = setTimeout(() => { setSearch(query.trim()); setPage(1); }, 300); return () => clearTimeout(timer); }, [query]);
  const updateType = (value: string) => { setType(value); setPage(1); };
  const updateCategory = (value: string) => { setCategory(value); setPage(1); };
  const updateOrdering = (value: string) => { setOrdering(value); setPage(1); };
  const updateAvailable = (value: boolean) => { setAvailable(value); setPage(1); };

  const complexes = useResource<ResidentialComplex[]>(user && (!user.is_resident_verified || changingResidence) ? "/auth/residential-complexes" : null, revision);
  const selectableComplexes = (complexes.data || []).filter(complex => !changingResidence || complex.id !== user?.residential_complex?.id);
  const activeResidentialComplexId = selectableComplexes.some(complex => String(complex.id) === residentialComplexId) ? residentialComplexId : String(selectableComplexes[0]?.id ?? "");
  const categories = useResource<Category[]>(user?.is_resident_verified ? "/categories" : null, revision);
  const listing = useResource<Listing>(user?.is_resident_verified && (view === "detail" || editing) && itemId ? `/listings/${itemId}` : null, revision);
  const selected = listing.data;
  const contacts = useResource<Contacts>(selected && user?.is_resident_verified && (modal === "contact" || editing) ? `/listings/${selected.id}/contacts` : null, revision);
  const matches = useResource<Page<Listing>>(user?.is_resident_verified && view === "detail" && selected ? `/listings/${selected.id}/matches?page=${matchPage}` : null, revision);
  const feed = useResource<Page<Listing>>(user?.is_resident_verified && (view === "explore" || view === "listings") ? `/listings?${qs(view === "listings" ? { mine: true, page, page_size: 12 } : { type, category: category === "all" ? undefined : category, search, available: available || undefined, ordering, page, page_size: 12 })}` : null, revision);
  const activity = useResource<Page<Activity>>(dashboard && user?.is_resident_verified ? `/activity?page=${activityPage}` : null, revision);
  const activeCreateCategory = createCategory || (editing && selected ? String(selected.category) : creating ? String(categories.data?.[0]?.id ?? "") : "");
  const activeCondition = condition || (editing && selected ? selected.condition : "good");

  async function run(action: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setFormError("");
    try { await action(); } catch (error) {
      if ((error as Error)?.name !== "AbortError") { const text = message(error); setFormError(text); toast.error(text); }
    } finally { busyRef.current = false; setBusy(false); }
  }
  function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget), email = String(data.get("email")), password = String(data.get("password"));
    void run(async () => {
      if (view === "register") {
        await api.register({ email, password, password_repeat: String(data.get("confirm")), first_name: String(data.get("first_name")).trim(), last_name: String(data.get("last_name")).trim() });
        // Registration succeeded independently of login: never ask the user to register again if login fails.
        toast.success("Account created. You can now sign in."); navigate("signin");
      }
      const account = await api.login(email, password);
      navigate(account.is_resident_verified ? returnTo : "verify");
      setReturnTo("dashboard");
      toast.success("Signed in.");
    });
  }
  function verifyResidence(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = String(new FormData(event.currentTarget).get("code") || "").trim();
    void run(async () => {
      await api.verifyResidence(Number(activeResidentialComplexId), code);
      invalidate();
      navigate("explore");
      toast.success(changingResidence ? "Residential complex changed. Your previous listings are hidden." : "Residential complex confirmed.");
    });
  }
  function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    void run(async () => { await api.updateProfile(Object.fromEntries(["first_name", "last_name", "address", "phone", "social_url"].map(key => [key, String(data.get(key) || "").trim()]))); navigate("profile"); toast.success("Profile saved."); });
  }
  function saveListing(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    void run(async () => {
      if (!activeCreateCategory) throw new ApiError(400, "Choose a category.");
      const payload = { type: editing ? selected?.type : createType, title: String(data.get("title")).trim(), description: String(data.get("description")).trim(), category: Number(activeCreateCategory), condition: activeCondition, duration: String(data.get("duration")).trim(), needed_until: data.get("needed_until") || null, neighborhood: String(data.get("neighborhood") || "").trim(), image_url: String(data.get("image_url") || "").trim(), contact_phone: String(data.get("contact_phone") || "").trim(), contact_social: String(data.get("contact_social") || "").trim() };
      const saved = await api.request<Listing>(editing ? `/listings/${selected?.id}` : "/listings", { method: editing ? "PATCH" : "POST", body: payload });
      invalidate(); openItem(saved.id); toast.success(editing ? "Listing updated." : "Listing published.");
    });
  }
  const showContact = () => { if (user) setModal("contact"); else signInFor(route); };
  const categoryOptions = (categories.data || []).map(c => ({ value: String(c.id), label: c.name }));
  const fieldError = formError ? <p role="alert" className="form-error">{formError}</p> : null;
  const feedContent = <><LoadState {...feed} retry={invalidate} />{!feed.loading && !feed.error && (feed.data?.results.length ? <div className="item-grid">{feed.data.results.map(item => <Card key={item.id} item={item} onOpen={openItem} />)}</div> : <div className="empty"><h2>{view === "listings" ? "No listings yet" : "No matching items"}</h2><p>{view === "listings" ? "Share something useful or ask a neighbor for help." : "Try another search or ask your neighbors."}</p><Button onClick={() => startCreate("request")}>Create a request</Button></div>)}<Pager data={feed.data} page={page} onChange={setPage} /></>;
  return <><Toaster position="bottom-right" /><header className="site-header"><a className="logo" href={user ? "#dashboard" : "#home"} aria-label="Neighborrow home">Neighborrow</a>{!user ? <><nav aria-label="Main navigation"><a href="#explore">Explore</a></nav><div className="button-row"><Button variant="outline" onClick={() => navigate("register")}>Register</Button><Button onClick={() => navigate("signin")}>Sign in</Button></div></> : !user.is_resident_verified ? <><nav aria-label="Main navigation"><a href="#verify">Confirm residential complex</a></nav><button className="user header-user" onClick={() => navigate("profile")}><span className="avatar" />{user.first_name || "My profile"}</button></> : <><nav aria-label="Main navigation"><a href="#explore">Explore</a><a href="#dashboard">Activity</a><a href="#listings">My listings</a></nav><SearchBox className="header-search" value={query} onChange={setQuery} onSubmit={searchNow} /><div className="button-row header-actions"><Button variant="outline" onClick={() => startCreate("offer")}>Offer item</Button><Button onClick={() => startCreate("request")}>Request item</Button></div><button className="user header-user" onClick={() => navigate("profile")}><span className="avatar" />{user.first_name || "My profile"}{user.last_name ? ` ${user.last_name.charAt(0)}.` : ""}</button></>}</header>
    <main className={`page ${view === "home" && !user ? "landing" : ""} ${dashboard ? "dashboard" : ""}`} aria-busy={busy}>
      {!modal && fieldError}
      {protectedPage && !user ? <div className="empty"><h1 className="blue">Sign in to continue</h1><p>Use your account to manage listings and your profile.</p><Button onClick={() => signInFor(route)}>Sign in</Button></div> :
      (needsResidence || changingResidence) ? <section className="auth">
        <div className="heading">
          <h1 className="blue">{changingResidence ? "Change residential complex" : "Confirm residential complex"}</h1>
          <p>{changingResidence ? "Enter the code for your new residential complex. Your previous listings will be hidden." : "Select your residential complex and enter its code."}</p>
        </div>
        <LoadState {...complexes} retry={invalidate} />
        {complexes.data && (selectableComplexes.length ? <form onSubmit={verifyResidence}>
          <fieldset className="auth-form" disabled={busy}>
            <label>Residential complex<Picker label="Residential complex" value={activeResidentialComplexId}
              onChange={setResidentialComplexId}
              options={selectableComplexes.map(complex => ({ value: String(complex.id), label: complex.name }))} /></label>
            <label>Residential complex code<Input name="code" type="password" required autoComplete="off"
              placeholder="Enter residential complex code" /></label>
            <Button type="submit" disabled={!selectableComplexes.some(complex => String(complex.id) === activeResidentialComplexId)}>
              {busy ? "Checking…" : changingResidence ? "Change residential complex" : "Confirm residential complex"}
            </Button>
          </fieldset>
        </form> : <p className="muted">{changingResidence ? "No other residential complexes are available yet." : "No residential complexes are available yet. Contact an administrator."}</p>)}
      </section> :
      view === "home" && !user ? <><section className="hero"><div className="heading"><h1>Find what you need nearby</h1><p>Borrow tools, share items, and help your neighbors.</p></div><SearchBox value={query} onChange={setQuery} onSubmit={searchNow} /><div className="hero-actions"><Button variant="secondary" onClick={() => navigate("explore")}>Explore</Button><Button onClick={() => startCreate("request")}>Request item</Button></div></section><section className="nearby"><div className="heading"><h1>Nearby offers</h1><p>Discover what&apos;s available in your neighborhood.</p></div><div className="empty"><h3>Confirm your residential complex to see nearby offers</h3><p>Create an account, sign in, and enter your complex code.</p></div></section><section className="share-cta"><div className="heading"><h1>Have something to share?</h1><p>Your unused tools could help someone nearby.</p></div><Button variant="secondary" onClick={() => startCreate("offer")}>Create an offer</Button></section></> :
      view === "explore" ? <><h1 className="blue">Explore</h1>{!user && <SearchBox value={query} onChange={setQuery} onSubmit={searchNow} />}<Tabs value={type} onValueChange={updateType} className="explore-tabs"><div className="explore-controls"><TabsList><TabsTrigger value="all">All</TabsTrigger><TabsTrigger value="request">Requests</TabsTrigger><TabsTrigger value="offer">Offers</TabsTrigger></TabsList><button className="filter-link" onClick={() => setFilters(!filters)} aria-expanded={filters}>Filters</button></div>{filters && <><LoadState {...categories} retry={invalidate} /><div className="filter-panel"><Picker label="Category" value={category} onChange={updateCategory} options={[{ value: "all", label: "All categories" }, ...categoryOptions]} /><Picker label="Sort" value={ordering} onChange={updateOrdering} options={[{ value: "newest", label: "Newest first" }, { value: "oldest", label: "Oldest first" }]} /><label className="checkbox-label"><Checkbox checked={available} onCheckedChange={checked => updateAvailable(checked === true)} />Available only</label><Button variant="secondary" onClick={() => { setQuery(""); updateCategory("all"); updateAvailable(false); updateOrdering("newest"); }}>Reset</Button></div></>}{["all", "request", "offer"].map(t => <TabsContent key={t} value={t}>{feedContent}</TabsContent>)}</Tabs></> :
      dashboard && user ? <><div className="dashboard-heading"><h1 className="blue">Dashboard</h1><div className="location"><span>{user.address || "Add your neighborhood"}</span><Button variant="secondary" onClick={() => setModal("location")}>Change</Button></div></div><section className="quick-section"><h3>Quick actions</h3><div className="quick-grid">{[{ title: "Create a request", text: "Ask neighbors for what you need", action: () => startCreate("request") }, { title: "Create an offer", text: "Share items with your neighbors", action: () => startCreate("offer") }, { title: "Explore requests", text: "See how you can help nearby", action: () => { updateType("request"); navigate("explore"); } }, { title: "Explore offers", text: "Find useful items near you", action: () => { updateType("offer"); navigate("explore"); } }].map((a, i) => <button className={`quick-card ${i % 2 === 0 ? "primary-card" : ""}`} key={a.title} onClick={a.action}><span className="quick-icon" /><h4>{a.title}</h4><p>{a.text}</p></button>)}</div></section><section className="activity-section"><div className="section-title"><h3>Recent activity</h3><button className="underlined" onClick={() => setHidden(!hidden)}>{hidden ? "Show" : "Hide"}</button></div>{!hidden && <><LoadState {...activity} retry={invalidate} />{activity.data && (activity.data.results.length ? <><div className="activity-table"><Table><TableHeader><TableRow>{["User", "Type", "Item", "Date & Time", "Description"].map(x => <TableHead key={x}>{x}</TableHead>)}</TableRow></TableHeader><TableBody>{activity.data.results.map((a, i) => <TableRow key={a.id}><TableCell><span className="user"><span className={`avatar ${i % 2 === 0 ? "pale" : ""}`} />{a.actor?.display_name || "Deleted account"}</span></TableCell><TableCell><span className={`activity-tag tag-${a.type.replaceAll("_", "-")}`}>{activityLabels[a.type] || a.type}</span></TableCell><TableCell>{a.listing ? <button className="text-link" onClick={() => openItem(a.listing!)}>{a.item_title}</button> : a.item_title}</TableCell><TableCell><time dateTime={a.created_at}>{dateLabel(a.created_at)}</time></TableCell><TableCell>{a.description}</TableCell></TableRow>)}</TableBody></Table></div><Pager data={activity.data} page={activityPage} onChange={setActivityPage} /></> : <div className="empty"><h3>No activity yet</h3><p>Create a listing or respond to a neighbor to get started.</p></div>)}</>}</section></> :
      view === "signin" || view === "register" ? <section className="auth"><div className="heading"><h1 className="blue">{view === "signin" ? "Sign in" : "Create an account"}</h1><p>{view === "signin" ? "Welcome back! Sign in to your account." : "Join your neighborhood and start sharing."}</p></div><form key={view} onSubmit={authenticate}><fieldset disabled={busy} className="auth-form">{view === "register" && <><label>Name<Input name="first_name" required maxLength={150} autoComplete="given-name" placeholder="Enter your name" /></label><label>Surname<Input name="last_name" required maxLength={150} autoComplete="family-name" placeholder="Enter your surname" /></label></>}<label>Email<Input name="email" type="email" required autoComplete="email" placeholder="Enter your email" /></label><label>Password<Input name="password" type="password" required minLength={view === "register" ? 8 : undefined} autoComplete={view === "signin" ? "current-password" : "new-password"} placeholder="Enter your password" /></label>{view === "register" && <label>Confirm password<Input name="confirm" type="password" required minLength={8} autoComplete="new-password" placeholder="Confirm your password" /></label>}<Button type="submit">{busy ? "Please wait…" : view === "signin" ? "Sign in" : "Register"}</Button><p className="auth-switch">{view === "signin" ? "Don’t have an account? " : "Already have an account? "}<a href={view === "signin" ? "#register" : "#signin"}>{view === "signin" ? "Register" : "Sign in"}</a></p><p className="preview-note">Your account and listings are saved. For now, sign in again after refreshing this page.</p></fieldset></form></section> :
      (view === "profile" || view === "profile-edit") && user ? <form onSubmit={saveProfile}><fieldset className="profile-page" disabled={busy}>{view === "profile" && <h3>Account information</h3>}<div className="profile-top"><div className="profile-person"><div className="profile-avatar" /><div><h2>{`${user.first_name} ${user.last_name}`.trim() || "My profile"}</h2><p>{user.email}</p></div></div>{view === "profile" ? <Button type="button" onClick={() => navigate("profile-edit")}>Edit profile</Button> : <div className="button-row"><Button variant="destructive" type="button" onClick={() => navigate("profile")}>Cancel</Button><Button type="submit">{busy ? "Saving…" : "Save changes"}</Button></div>}</div><div className="profile-fields" key={`${view}-${user.id}`}>{([['first_name', 'Name'], ['last_name', 'Surname'], ['email', 'Email'], ['address', 'Address'], ['phone', 'Phone'], ['social_url', 'Social profile link']] as const).map(([key, label]) => <label key={key}>{label}<Input name={key} type={key === "email" ? "email" : key === "social_url" ? "url" : key === "phone" ? "tel" : "text"} defaultValue={user[key]} readOnly={view === "profile" || key === "email"} maxLength={key === "social_url" ? 500 : key === "phone" ? 12 : key === "address" ? 255 : 150} minLength={key === "phone" ? 12 : undefined} pattern={key === "phone" ? phonePattern : undefined} title={key === "phone" ? "Use +7 followed by 10 digits" : undefined} placeholder={key === "phone" ? "+7XXXXXXXXXX" : undefined} /></label>)}<label>Residential complex<Input value={user.residential_complex?.name || "Not confirmed"} readOnly /></label></div>{view === "profile" && <div className="account-settings"><section><h3>Account settings</h3><div className="button-row"><Button variant="secondary" type="button" onClick={() => setModal("password")}>Change password</Button><Button variant="secondary" type="button" onClick={() => navigate("listings")}>My listings</Button><Button variant="secondary" type="button" onClick={() => navigate("change-residence")}>Change residential complex</Button></div></section><section><h3>Account actions</h3><div className="button-row"><Button variant="outline" type="button" onClick={() => void run(async () => { try { await api.logout(); } finally { navigate("home"); } })}>Logout</Button><Button variant="destructive" type="button" onClick={() => setModal("delete")}>Delete account</Button></div></section></div>}<p className="preview-note">Your profile contacts are private. Choose what to share in each listing.</p></fieldset></form> :
      (creating || editing) && user ? <><h1 className="blue">{editing ? "Edit listing" : createType === "request" ? "Create a request" : "Create an offer"}</h1><LoadState loading={categories.loading || (editing && (listing.loading || contacts.loading))} error={categories.error || (editing ? listing.error || contacts.error : "")} retry={invalidate} />{(!editing || (selected && contacts.data)) && categories.data && (editing && selected?.owner.id !== user.id ? <div className="empty"><p>You can only edit your own listings.</p><Button onClick={() => openItem(selected!.id)}>Back to item</Button></div> : <form key={editing ? selected?.id : createType} onSubmit={saveListing}><fieldset className="listing-form" disabled={busy}><label>{(editing ? selected?.type : createType) === "request" ? "What do you need?" : "What would you like to share?"}<Input name="title" placeholder="e.g. 3m Ladder" required maxLength={100} defaultValue={editing ? selected?.title : ""} /></label><label className="category-field">Category<Picker label="Category" value={activeCreateCategory} onChange={setCreateCategory} options={categoryOptions} /></label><label>Description<textarea name="description" placeholder="Tell your neighbors a little more..." required rows={4} maxLength={2000} defaultValue={editing ? selected?.description : ""} /></label><div className="form-row"><label>When and for how long?<Input name="duration" placeholder="e.g. Today, for 2 hours" required maxLength={100} defaultValue={editing ? selected?.duration : ""} /></label><label>Condition<Picker label="Condition" value={activeCondition} onChange={setCondition} options={Object.entries(conditions).map(([value, label]) => ({ value, label }))} /></label></div><div className="form-row"><label>Needed until (optional)<Input type="date" name="needed_until" defaultValue={editing ? selected?.needed_until || "" : ""} /></label><label>Neighborhood<Input name="neighborhood" maxLength={150} placeholder="e.g. Almaly, Almaty" defaultValue={editing ? selected?.neighborhood : ""} /></label></div><label>Photo URL (optional)<Input name="image_url" type="url" maxLength={1000} placeholder="https://…" defaultValue={editing ? selected?.image_url : ""} /></label><div className="form-row"><label>Contact phone (optional)<Input name="contact_phone" type="tel" minLength={12} maxLength={12} pattern={phonePattern} title="Use +7 followed by 10 digits" placeholder="+7XXXXXXXXXX" defaultValue={editing ? contacts.data?.phone : ""} /></label><label>Social profile link (optional)<Input name="contact_social" type="url" maxLength={500} placeholder="https://…" defaultValue={editing ? contacts.data?.social_url : ""} /></label></div><p className="preview-note">The contacts entered here will be visible to signed-in neighbors.</p><div className="button-row"><Button type="submit" disabled={!activeCreateCategory}>{busy ? "Saving…" : editing ? "Save changes" : createType === "request" ? "Create request" : "Create offer"}</Button><Button type="button" variant="outline" onClick={() => navigate("listings")}>Cancel</Button></div></fieldset></form>)}</> :
      view === "detail" ? <><a href="#explore" className="text-link">Back to Explore</a>{!itemId ? <div className="empty">This listing could not be found.</div> : <LoadState {...listing} retry={invalidate} />}{selected && <><div className="detail-grid"><div className="detail-image"><ListingPhoto url={selected.image_url} title={selected.title} /></div><section className="detail-panel"><div className="section-title"><h2>{selected.title}</h2><time className="muted small-text" dateTime={selected.created_at}>{dateLabel(selected.created_at)}</time></div><h4 className="muted">{selected.type === "request" ? "Request" : "Offer"}</h4><p className="small-text">{selected.description}</p><dl className="detail-facts"><div><dt>Category</dt><dd>{selected.category_name}</dd></div><div><dt>Availability</dt><dd>{isAvailable(selected) ? "Available" : "Unavailable"}</dd></div><div><dt>Duration</dt><dd>{selected.duration}</dd></div><div><dt>Condition</dt><dd>{conditions[selected.condition]}</dd></div>{selected.needed_until && <div><dt>Needed until</dt><dd>{deadlineLabel(selected.needed_until)}</dd></div>}{selected.neighborhood && <div><dt>Neighborhood</dt><dd>{selected.neighborhood}</dd></div>}</dl><div className="detail-person"><span className="user"><span className="avatar pale" />{selected.owner.display_name}</span>{selected.owner.id === user?.id && <span className="muted">Your listing</span>}</div><div className="button-row">{selected.owner.id !== user?.id && <Button disabled={busy || !isAvailable(selected) || selected.has_responded} onClick={() => user ? setModal("respond") : signInFor(route)}>{selected.has_responded ? "Response saved" : selected.type === "offer" ? "Request item" : "Offer help"}</Button>}<Button variant="secondary" onClick={showContact}>Show contacts</Button></div>{selected.owner.id === user?.id && <div className="button-row"><Button variant="outline" disabled={busy} onClick={() => { setCreateCategory(""); setCondition(""); navigate(`edit/${selected.id}`); }}>Edit listing</Button><Button variant="secondary" disabled={busy} onClick={() => void run(async () => { await api.request(`/listings/${selected.id}`, { method: "PATCH", body: { available: !selected.available } }); invalidate(); toast.success("Availability updated."); })}>{selected.available ? "Mark unavailable" : "Mark available"}</Button><Button variant="destructive" disabled={busy} onClick={() => setModal("delete-listing")}>Delete</Button></div>}</section></div><section className="matching"><h3>{selected.type === "request" ? "Offers in this category" : "Requests in this category"}</h3><LoadState {...matches} retry={invalidate} />{matches.data && (matches.data.results.length ? <div className="item-grid">{matches.data.results.map(item => <Card key={item.id} item={item} onOpen={openItem} />)}</div> : <p className="muted">No matching listings yet.</p>)}<Pager data={matches.data} page={matchPage} onChange={setMatchPage} /></section></>}</> :
      view === "listings" ? <><div className="section-title"><h1 className="blue">My listings</h1><Button onClick={() => startCreate("offer")}>Create an offer</Button></div>{feedContent}</> : <div className="empty"><h1>404</h1><p>This page could not be found.</p><Button onClick={() => navigate("home")}>Back to home</Button></div>}
    </main><footer className="preview-footer">Neighborrow · Borrow, share, help nearby.</footer>
    <Dialog open={!!modal && !["delete", "delete-listing"].includes(modal)} onOpenChange={open => { if (!open && !busy) { setModal(""); setFormError(""); } }}><DialogContent><DialogHeader><DialogTitle>{{ location: "Your neighborhood", respond: "Respond to this listing", contact: "Contact details", password: "Change password" }[modal] || "Neighborrow"}</DialogTitle><DialogDescription>{modal === "location" ? "Update the address shown in your dashboard." : modal === "respond" ? "Your response will appear in your neighbor’s activity. Use their shared contacts to arrange the details." : modal === "contact" ? "Contact information shared by the owner of this listing." : "Enter your current password and choose a new one. You’ll need to sign in again."}</DialogDescription></DialogHeader>{fieldError}
      {modal === "location" && <form onSubmit={e => { e.preventDefault(); const address = String(new FormData(e.currentTarget).get("address")).trim(); void run(async () => { await api.updateProfile({ address }); setModal(""); toast.success("Address saved."); }); }}><fieldset className="modal-form" disabled={busy}><label>Address<Input name="address" maxLength={255} defaultValue={user?.address} /></label><Button>{busy ? "Saving…" : "Save"}</Button></fieldset></form>}
      {modal === "respond" && selected && <Button disabled={busy} onClick={() => void run(async () => { const result = await api.request<{ created: boolean }>(`/listings/${selected.id}/interest`, { method: "POST" }); setModal(""); invalidate(); toast.success(result.created ? "Response saved. Your neighbor can see it in their activity." : "You have already responded."); })}>{busy ? "Saving…" : "Confirm response"}</Button>}
      {modal === "contact" && <><LoadState {...contacts} retry={invalidate} />{contacts.data && <div className="contact-details">{contacts.data.phone && <p><strong>Phone</strong><span>{contacts.data.phone}</span></p>}{safeLink(contacts.data.social_url) && <p><strong>Social profile</strong><a href={safeLink(contacts.data.social_url)!} target="_blank" rel="noopener noreferrer">Open profile ↗</a></p>}{!contacts.data.phone && !safeLink(contacts.data.social_url) && <p>The owner has not shared contact information.</p>}</div>}</>}
      {modal === "password" && <form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void run(async () => { await api.changePassword(String(f.get("current_password")), String(f.get("new_password")), String(f.get("new_password_repeat"))); navigate("signin"); toast.success("Password changed. Please sign in again."); }); }}><fieldset className="modal-form" disabled={busy}><label>Current password<Input type="password" name="current_password" required autoComplete="current-password" /></label><label>New password<Input type="password" name="new_password" required minLength={8} autoComplete="new-password" /></label><label>Confirm new password<Input type="password" name="new_password_repeat" required minLength={8} autoComplete="new-password" /></label><Button>{busy ? "Saving…" : "Change password"}</Button></fieldset></form>}
    </DialogContent></Dialog>
    <AlertDialog open={modal === "delete" || modal === "delete-listing"} onOpenChange={open => { if (!open && !busy) { setModal(""); setFormError(""); } }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{modal === "delete" ? "Delete your account?" : "Delete this listing?"}</AlertDialogTitle><AlertDialogDescription>{modal === "delete" ? "Your account and all your listings will be permanently deleted. Enter your current password to confirm." : "This listing will be permanently removed. This cannot be undone."}</AlertDialogDescription></AlertDialogHeader>{fieldError}<form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void run(async () => { if (modal === "delete") { await api.deleteAccount(String(f.get("current_password"))); navigate("home"); toast.success("Account deleted."); } else if (selected) { await api.request(`/listings/${selected.id}`, { method: "DELETE" }); setModal(""); invalidate(); navigate("listings"); toast.success("Listing deleted."); } }); }}><fieldset className="modal-form" disabled={busy}>{modal === "delete" && <label>Current password<Input type="password" name="current_password" required autoComplete="current-password" /></label>}<AlertDialogFooter><AlertDialogCancel type="button">Cancel</AlertDialogCancel><Button variant="destructive" type="submit">{busy ? "Deleting…" : modal === "delete" ? "Delete account" : "Delete listing"}</Button></AlertDialogFooter></fieldset></form></AlertDialogContent></AlertDialog>
  </>;
}
