import { useEffect, useRef, useState } from 'react'
import { Bell, BriefcaseBusiness, Building2, CalendarDays, CircleAlert, Download, Heart, LogOut, MapPin, Menu, PanelLeftClose, PanelLeftOpen, Pencil, Plus, Search, Sparkles, Star, Trash2, Users, X, MailCheck } from 'lucide-react'
import CompanyForm from './CompanyForm'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    const detail = Array.isArray(error.detail)
      ? error.detail.map((item) => item.msg || JSON.stringify(item)).join(', ')
      : typeof error.detail === 'string'
        ? error.detail
        : error.detail?.msg || 'Something went wrong. Please try again.'
    throw new Error(detail)
  }
  return response.status === 204 ? null : response.json()
}

function App() {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem('drive-manager-user') || 'null'))
  const [authMode, setAuthMode] = useState('login')
  const [companies, setCompanies] = useState([])
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('All opportunities')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingCompany, setEditingCompany] = useState(null)
  const [activeView, setActiveView] = useState('opportunities')
  const [users, setUsers] = useState([])
  const [interestSummary, setInterestSummary] = useState([])
  const [pendingOpportunities, setPendingOpportunities] = useState([])
  const [gmailStatus, setGmailStatus] = useState({ connected: false })
  const [gmailBusy, setGmailBusy] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [installPrompt, setInstallPrompt] = useState(null)
  const [selectedYear, setSelectedYear] = useState(() => Number(localStorage.getItem('drive-manager-year') || 2027))
  const notificationRef = useRef(null)

  useEffect(() => {
    const captureInstallPrompt = (event) => {
      event.preventDefault()
      setInstallPrompt(event)
    }
    window.addEventListener('beforeinstallprompt', captureInstallPrompt)
    return () => window.removeEventListener('beforeinstallprompt', captureInstallPrompt)
  }, [])

  useEffect(() => {
    if (!notificationsOpen) return
    const closeOnOutsideClick = (event) => {
      if (!notificationRef.current?.contains(event.target)) setNotificationsOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setNotificationsOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [notificationsOpen])

  useEffect(() => {
    const savedToken = localStorage.getItem('drive-manager-token')
    if (!savedToken) return
    request('/user/me', { headers: { Authorization: `Bearer ${savedToken}` } })
      .then((currentUser) => {
        setUser(currentUser)
        localStorage.setItem('drive-manager-user', JSON.stringify(currentUser))
        setToken(savedToken)
      })
      .catch(() => {
        localStorage.removeItem('drive-manager-token')
        localStorage.removeItem('drive-manager-user')
      })
  }, [])

  async function loadCompanies() {
    setLoading(true)
    setError('')
    try {
      setCompanies(await request('/company/', { headers: { Authorization: `Bearer ${token}` } }) || [])
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!token) return
    loadCompanies()
  }, [token])

  useEffect(() => {
    if (!token || !user || user.role?.toLowerCase() !== 'spc') return
    const headers = { Authorization: `Bearer ${token}` }
    if (activeView === 'users') request('/user/', { headers }).then(setUsers).catch((e) => setError(e.message))
    if (activeView === 'interest') request('/company/interest-summary', { headers }).then(setInterestSummary).catch((e) => setError(e.message))
    if (activeView === 'email-review') {
      const refreshReview = () => {
        request('/api/admin/placement/pending/', { headers }).then(setPendingOpportunities).catch((e) => setError(e.message))
        request('/api/integrations/gmail/status', { headers }).then(setGmailStatus).catch((e) => setError(e.message))
      }
      refreshReview()
      const timer = window.setInterval(refreshReview, 30000)
      return () => window.clearInterval(timer)
    }
  }, [token, user, activeView])

  function handleAuthenticated(nextToken, nextUser) {
    localStorage.setItem('drive-manager-token', nextToken)
    localStorage.setItem('drive-manager-user', JSON.stringify(nextUser))
    setToken(nextToken)
    setUser(nextUser)
  }

  function handleLogout() {
    localStorage.removeItem('drive-manager-token')
    localStorage.removeItem('drive-manager-user')
    setToken(null)
    setUser(null)
    setCompanies([])
  }

  if (!token) return <AuthScreen onAuthenticated={handleAuthenticated} />

  const isSpc = user?.role?.toLowerCase() === 'spc'
  const visibleCompanies = companies.filter((company) => (isSpc || company.process !== 'send_mail') && (isSpc || (company.year_of_passing || 2027) === selectedYear) && [company.name, company.location, company.process].join(' ').toLowerCase().includes(search.toLowerCase()) && (activeFilter === 'All opportunities' || company.process === activeFilter))
  const savedOpportunities = companies
    .filter((company) => company.interested)
    .sort((a, b) => new Date(a.date) - new Date(b.date))
  const now = Date.now()
  const upcomingCount = savedOpportunities.filter((company) => {
    const timeUntil = new Date(company.date).getTime() - now
    return timeUntil >= 0 && timeUntil <= 7 * 24 * 60 * 60 * 1000
  }).length

  function selectView(view) {
    setActiveView(view)
    setSidebarOpen(false)
  }

  async function installApp() {
    if (!installPrompt) return
    await installPrompt.prompt()
    await installPrompt.userChoice
    setInstallPrompt(null)
  }

  async function toggleInterest(companyId) {
    const company = companies.find((item) => item.id === companyId)
    if (company && new Date(company.date).getTime() <= Date.now()) return
    try {
      await request(`/company/interested/${companyId}`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}` } })
      setCompanies((current) => current.map((company) => company.id === companyId ? { ...company, interested: !company.interested } : company))
    } catch (requestError) { setError(requestError.message) }
  }

  async function saveCompany(formData) {
    try {
      const editing = Boolean(editingCompany)
      const saved = await request(editing ? `/company/${editingCompany.id}` : '/company/', { method: editing ? 'PATCH' : 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(formData) })
      setCompanies((current) => editing ? current.map((company) => company.id === saved.id ? { ...company, ...saved } : company) : [...current, saved])
      setShowForm(false)
      setEditingCompany(null)
    } catch (requestError) { setError(requestError.message) }
  }

  async function deleteCompany(company) {
    if (!window.confirm(`Delete ${company.name}? This will also remove its saved interest and reminder.`)) return
    try {
      await request(`/company/${company.id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
      setCompanies((current) => current.filter((item) => item.id !== company.id))
    } catch (requestError) { setError(requestError.message) }
  }

  async function changeRole(targetUser, role) {
    try {
      const updated = await request(`/user/${targetUser.id}/role`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ role, year_of_passing: targetUser.year_of_passing }) })
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (requestError) { setError(requestError.message) }
  }

  async function changeUserYear(targetUser, year) {
    try {
      const updated = await request(`/user/${targetUser.id}/role`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ role: targetUser.role, year_of_passing: year ? Number(year) : null }) })
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (requestError) { setError(requestError.message) }
  }

  async function runGmailAction(action) {
    setGmailBusy(true)
    try {
      if (action === 'connect') {
        const authorization = await request('/api/integrations/gmail/connect', {
          method: 'POST', headers: { Authorization: `Bearer ${token}` },
        })
        window.location.assign(authorization.authorization_url)
        return
      }
      const result = await request(action === 'disconnect' ? '/api/integrations/gmail/disconnect' : `/api/admin/integrations/gmail/${action}`, {
        method: action === 'disconnect' ? 'DELETE' : 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (action === 'sync') setError(`Mailbox sync checked ${result.fetched} messages, queued ${result.placement_opportunities} placement opportunities for SPC review, and ignored ${result.ignored_sender} messages from outside RVCE.`)
      const status = await request('/api/integrations/gmail/status', { headers: { Authorization: `Bearer ${token}` } })
      setGmailStatus(status)
    } catch (requestError) { setError(requestError.message) } finally { setGmailBusy(false) }
  }

  function openDuplicateMatch(match) {
    if (match.record_type === 'PENDING') {
      document.getElementById(`pending-opportunity-${match.record_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setSearch('')
    setActiveFilter('All opportunities')
    setActiveView('companies')
    window.setTimeout(() => document.getElementById(`published-company-${match.record_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100)
  }

  return (
    <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${sidebarOpen ? 'sidebar-visible' : ''}`}>
      {sidebarOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <aside className="sidebar" aria-label="Main navigation">
        <div className="sidebar-top"><div className="brand"><span className="brand-mark"><Sparkles size={16} /></span><span>Drive<span className="brand-light">board</span></span></div><button className="sidebar-collapse" aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={() => setSidebarCollapsed((value) => !value)}>{sidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}</button></div>
        <div className="profile-card"><div className="avatar">{user?.name?.slice(0, 1).toUpperCase()}</div><div><strong>{user?.name}</strong><span>{isSpc ? 'SPC coordinator' : 'Student'}</span></div></div>
        <div className="side-label">Workspace</div>
        <nav className="side-nav">
          {isSpc ? <button className={`nav-item ${activeView === 'companies' ? 'active' : ''}`} onClick={() => selectView('companies')} title="Manage companies"><Building2 size={18} /><span className="nav-label">Manage companies</span></button> : <button className={`nav-item ${activeView === 'opportunities' ? 'active' : ''}`} onClick={() => selectView('opportunities')} title="Opportunities"><BriefcaseBusiness size={18} /><span className="nav-label">Opportunities</span><span className="nav-count">{companies.length}</span></button>}
          {isSpc && <>
            <button className={`nav-item ${activeView === 'users' ? 'active' : ''}`} onClick={() => selectView('users')} title="Manage users"><Users size={18} /><span className="nav-label">Manage users</span></button>
            <button className={`nav-item ${activeView === 'interest' ? 'active' : ''}`} onClick={() => selectView('interest')} title="Drive interest"><Heart size={18} /><span className="nav-label">Drive interest</span></button>
            <button className={`nav-item ${activeView === 'email-review' ? 'active' : ''}`} onClick={() => selectView('email-review')} title="Email review"><MailCheck size={18} /><span className="nav-label">Email review</span></button>
          </>}
        </nav>
        <div className="sidebar-spacer" />
        {installPrompt && <button className="sidebar-action install-action" onClick={installApp}><Download size={17} /><span>Install app</span></button>}
        <button className="sidebar-action signout-action" onClick={handleLogout}><LogOut size={17} /><span>Sign out</span></button>
        <div className="sidebar-footnote">Driveboard · Campus opportunity desk</div>
      </aside>
      <main className="main-content" id="opportunities">
        <header className="topbar"><div className="topbar-leading"><button className="nav-toggle" aria-label="Open navigation" title="Open navigation" onClick={() => { setSidebarOpen(true); setSidebarCollapsed(false) }}><Menu size={20} /></button><div className="eyebrow">{isSpc ? 'Coordinator workspace' : 'Your opportunity desk'}</div></div><div className="topbar-actions"><div className="notification-wrap" ref={notificationRef}><button className={`icon-button notification-button ${notificationsOpen ? 'selected' : ''}`} title="Saved opportunities and upcoming dates" aria-label={`Notifications${upcomingCount ? `, ${upcomingCount} upcoming` : ''}`} aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}><Bell size={19} />{upcomingCount > 0 && <span className="notification-badge">{upcomingCount}</span>}</button>{notificationsOpen && <section className="notification-panel" aria-label="Saved opportunities"><div className="notification-panel-header"><div><span className="section-kicker">Your board</span><h2>Saved opportunities</h2></div><button className="notification-close" onClick={() => setNotificationsOpen(false)} aria-label="Close notifications"><X size={17} /></button></div>{savedOpportunities.length ? <div className="notification-list">{savedOpportunities.map((company) => <article className="notification-item" key={company.id}><span className="notification-mark"><CalendarDays size={16} /></span><div><strong>{company.name}</strong><span>{company.location}</span><small>{new Date(company.date).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</small></div></article>)}</div> : <p className="notification-empty">Save an opportunity with the heart button and its date will show up here.</p>}</section>}</div></div></header>
        <section className="welcome-row"><div><p className="kicker">Good morning, {user?.name?.split(' ')[0] || 'there'}</p><h1>Find the right <em>next move.</em></h1><p className="subhead">Discover companies, mark your interest, and stay ready for what is coming.</p></div><div className="date-stamp"><CalendarDays size={17} /><span>October 2026<br /><strong>Campus season</strong></span></div></section>
        <section className="stats-row"><div className="stat"><span className="stat-icon coral"><BriefcaseBusiness size={18} /></span><div><strong>{companies.length}</strong><span>open opportunities</span></div></div><div className="stat"><span className="stat-icon blue"><Heart size={18} /></span><div><strong>{companies.filter((company) => company.interested).length}</strong><span>students engaged</span></div></div><div className="stat"><span className="stat-icon gold"><Star size={18} /></span><div><strong>Ready</strong><span>your profile status</span></div></div></section>
        {error && <div className="error-banner"><CircleAlert size={18} />{error}<button onClick={() => setError('')}><X size={16} /></button></div>}
        {activeView === 'email-review' && isSpc ? <><section className="section-heading"><div><span className="section-kicker">SPC tools · Gmail integration</span><h2>Placement email review</h2></div></section><article className="interest-panel gmail-settings"><div><strong>{gmailStatus.connected ? (gmailStatus.watch_expiration ? "Gmail connected · watch active" : "Gmail connected · starting watch") : "Gmail not connected"}</strong><span>{gmailStatus.email_address || "Mailbox: maaryamannp.mca25@rvce.edu.in"}</span><small>Last sync: {gmailStatus.last_sync_at ? new Date(gmailStatus.last_sync_at).toLocaleString() : "Pending first sync"} · Watch expires: {gmailStatus.watch_expiration ? new Date(gmailStatus.watch_expiration).toLocaleString() : "Starting automatically"}</small>{gmailStatus.last_error && <small className="review-warning">{gmailStatus.last_error}</small>}</div><div className="review-actions">{!gmailStatus.connected ? <button className="primary-button" disabled={gmailBusy} onClick={() => runGmailAction("connect")}>Connect Gmail</button> : <><button className="secondary-button" disabled={gmailBusy} onClick={() => runGmailAction("watch")}>Start / renew watch</button><button className="secondary-button" disabled={gmailBusy} onClick={() => runGmailAction("sync")}>Sync mailbox</button><button className="secondary-button" disabled={gmailBusy} onClick={() => runGmailAction("disconnect")}>Disconnect</button></>}</div></article><p className="review-intro">New inbox messages are checked automatically. Emails from @rvce.edu.in are classified and placement details are sent here for SPC review; nothing is published to students until an SPC approves it.</p>{pendingOpportunities.length ? <div className="interest-list">{pendingOpportunities.map((item) => <ReviewOpportunity key={item.id} item={item} token={token} onUpdate={(updated) => setPendingOpportunities((items) => items.map((current) => current.id === updated.id ? updated : current))} onError={(message) => setError(message)} onOpenMatch={openDuplicateMatch} />)}</div> : <div className="empty-state"><MailCheck size={30} /><strong>No pending opportunities</strong><span>New review items will be listed here.</span></div>}</> : activeView === 'users' && isSpc ? <><section className="section-heading"><div><span className="section-kicker">SPC tools</span><h2>People on Driveboard</h2></div></section><div className="management-list">{users.map((person) => <article className="management-row" key={person.id}><div className="user-avatar">{person.name.slice(0, 1).toUpperCase()}</div><div className="management-details"><strong>{person.name}</strong><span>{person.email}</span></div><span className={`role-badge ${person.role.toLowerCase()}`}>{person.role}</span><select aria-label={`Role for ${person.name}`} value={person.role} onChange={(event) => changeRole(person, event.target.value)}><option value="STUDENT">Student</option><option value="SPC">SPC coordinator</option></select><select aria-label={`Year of passing for ${person.name}`} value={person.year_of_passing || ''} onChange={(event) => changeUserYear(person, event.target.value)}><option value="">Unassigned</option><option value="2027">2027</option><option value="2028">2028</option></select></article>)}</div></> : activeView === 'interest' && isSpc ? <><section className="section-heading"><div><span className="section-kicker">SPC tools</span><h2>Interest by drive</h2></div></section><div className="interest-list">{interestSummary.map((drive) => <article className="interest-panel" key={drive.company_id}><div className="interest-heading"><div><span className="process-tag">{drive.process.replace('_', ' ')}</span><h3>{drive.company_name}</h3><span className="company-meta">{drive.location} · {new Date(drive.date).toLocaleDateString()}</span></div><span className="interest-count">{drive.interested_users.length} interested</span></div>{drive.interested_users.length ? <div className="interested-people">{drive.interested_users.map((person) => <span className="person-chip" key={person.id}>{person.name} <small>{person.email}</small></span>)}</div> : <p className="no-interest">No students have marked interest yet.</p>}</article>)}</div></> : <><section className="section-heading"><div><span className="section-kicker">Explore the board</span><h2>Open opportunities</h2></div>{isSpc && <button className="primary-button" onClick={() => { setEditingCompany(null); setShowForm(true) }}><Plus size={17} /> Add company</button>}</section></>}
        <div className="toolbar">{!isSpc && <label className="year-picker">Year of passing<select value={selectedYear} onChange={(event) => { const year = Number(event.target.value); setSelectedYear(year); localStorage.setItem('drive-manager-year', String(year)) }}><option value={2027}>2027</option><option value={2028}>2028</option></select></label>}<label className="search-field"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search company, place or process" /></label><div className="filter-pills">{['All opportunities', 'online_assesment', 'interview', 'ppt', 'group_discussion', 'pen_paper_test', 'technical_assessment', ...(isSpc ? ['send_mail'] : [])].map((filter) => <button key={filter} className={activeFilter === filter ? 'filter active' : 'filter'} onClick={() => setActiveFilter(filter)}>{filter.replaceAll('_', ' ')}</button>)}</div></div>
        {activeView !== 'email-review' && (loading ? <div className="empty-state"><div className="spinner" />Loading opportunities...</div> : visibleCompanies.length ? <div className="company-grid">{visibleCompanies.map((company, index) => <CompanyCard key={company.id} company={company} index={index} isSpc={isSpc} onToggle={toggleInterest} onEdit={(selected) => { setEditingCompany(selected); setShowForm(true) }} onDelete={deleteCompany} />)}</div> : <div className="empty-state"><Building2 size={30} /><strong>No opportunities yet</strong><span>Try another search or check back later.</span></div>)}
        <footer className="footer"><span>Driveboard · Built for thoughtful next steps</span><span>Student placement workspace</span></footer>
      </main>
      {showForm && <CompanyForm company={editingCompany} onClose={() => { setShowForm(false); setEditingCompany(null) }} onSave={saveCompany} />}
    </div>
  )
}


function AuthScreen({ onAuthenticated }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [googleReady, setGoogleReady] = useState(false)
  const buttonContainer = useRef(null)
  const loginCallback = useRef(null)

  useEffect(() => {
    loginCallback.current = handleGoogle
  })

  useEffect(() => {
    if (!import.meta.env.VITE_GOOGLE_CLIENT_ID) {
      setError('Google sign-in is not configured yet. Set VITE_GOOGLE_CLIENT_ID.');
      return
    }
    let cancelled = false
    let initializedHere = false
    let script = document.querySelector('script[data-driveboard-google="true"]')
    const render = () => {
      if (cancelled || !window.google?.accounts?.id || !buttonContainer.current) return
      if (!window.__driveboardGoogleInitialized) {
        window.google.accounts.id.initialize({
          client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
          callback: (response) => loginCallback.current?.(response),
        })
        window.__driveboardGoogleInitialized = true
        initializedHere = true
      }
      const host = document.createElement('div')
      buttonContainer.current.replaceChildren(host)
      window.google.accounts.id.renderButton(host, {
        theme: 'outline', size: 'large', text: 'continue_with', shape: 'rectangular', width: 390,
      })
      setGoogleReady(true)
    }
    if (window.google?.accounts?.id) render()
    else {
      if (!script) {
        script = document.createElement('script')
        script.src = 'https://accounts.google.com/gsi/client'
        script.async = true
        script.dataset.driveboardGoogle = 'true'
        script.addEventListener('load', render, { once: true })
        script.addEventListener('error', () => setError('Unable to load Google sign-in. Please check your connection and try again.'), { once: true })
        document.head.appendChild(script)
      } else if (window.google?.accounts?.id) render()
      else script.addEventListener('load', render, { once: true })
    }
    return () => {
      cancelled = true
      buttonContainer.current?.replaceChildren()
      if (initializedHere) {
        window.__driveboardGoogleInitialized = false
        window.google?.accounts?.id?.cancel?.()
      }
    }
  }, [])
  async function handleGoogle(credentialResponse) {
    setBusy(true); setError('')
    try {
      const result = await request('/user/google', { method: 'POST', body: JSON.stringify({ credential: credentialResponse.credential }) })
      const currentUser = await request('/user/me', { headers: { Authorization: `Bearer ${result.access_token}` } })
      onAuthenticated(result.access_token, currentUser)
    } catch (requestError) { setError(requestError.message) } finally { setBusy(false) }
  }
  return <div className="auth-shell"><div className="auth-aside"><div className="brand"><span className="brand-mark"><Sparkles size={16} /></span><span>Drive<span className="brand-light">board</span></span></div><div className="auth-quote"><span className="quote-mark">“</span><h1>Small steps.<br /><em>Good direction.</em></h1><p>A calmer way to find the companies and opportunities that fit your next chapter.</p></div><div className="aside-footer"><span>01 / 03</span><span>Student opportunity desk</span></div></div><main className="auth-main"><div className="auth-form-wrap"><span className="section-kicker">Welcome</span><h2>Sign in to your board</h2><p className="form-intro">Use your verified RVCE Google account.</p>{error && <div className="error-banner"><CircleAlert size={17} />{error}</div>}<div className="google-login-wrap">{busy ? <div className="empty-state"><div className="spinner" />Signing in...</div> : <><div ref={buttonContainer} className="google-signin-host" />{!googleReady && <span className="google-signin-placeholder">Loading Google sign-in…</span>}</>}</div></div></main></div>
}

function ReviewOpportunity({ item, token, onUpdate, onError, onOpenMatch }) {
  async function act(action, payload) {
    try {
      const updated = await request(`/api/admin/placement/pending/${item.id}${action}`, {
        method: action ? 'POST' : 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      })
      onUpdate(updated)
    } catch (error) { onError(error.message) }
  }
  return <article id={`pending-opportunity-${item.id}`} className="interest-panel review-card">
    <div className="interest-heading"><div><span className={`review-status ${item.eligibility_status.toLowerCase()}`}>{item.eligibility_status.replaceAll('_', ' ')}</span><h3>{item.company_name}{item.job_title ? ` · ${item.job_title}` : ''}</h3><span className="company-meta">{item.opportunity_type || 'Placement opportunity'} · {item.location || 'Location not specified'}</span></div><span className="role-badge">{item.review_status}</span></div>
    {item.possible_duplicates?.length > 0 && <div className="duplicate-warning" role="note"><strong>Possible duplicate</strong><span>Same normalized company, process, and date found:</span><ul>{item.possible_duplicates.map((match) => <li key={`${match.record_type}-${match.record_id}-${match.process}-${match.event_date}`}><button type="button" onClick={() => onOpenMatch(match)}>Open {match.record_type === 'PENDING' ? 'pending review' : 'published company'} #{match.record_id}</button><span>{match.company_name} · {match.process.replaceAll('_', ' ')} · {new Date(match.event_date).toLocaleDateString()}</span></li>)}</ul></div>}
    {item.description && <p className="review-copy">{item.description}</p>}
    <div className="review-facts"><span>Department submission: {item.department_submission_date ? new Date(item.department_submission_date).toLocaleString() : 'Not specified'}</span><span>OA: {item.assessment_date ? new Date(item.assessment_date).toLocaleString() : 'Not specified'}</span><span>GD: {item.group_discussion_date ? new Date(item.group_discussion_date).toLocaleString() : 'Not specified'}</span><span>Interview dates: {item.interview_dates?.length ? item.interview_dates.map((date) => new Date(date).toLocaleString()).join(', ') : item.interview_date ? new Date(item.interview_date).toLocaleString() : 'Not specified'}</span><span>Application deadline: {item.application_deadline ? new Date(item.application_deadline).toLocaleString() : 'Not specified'}</span><span>Courses: {item.eligible_courses.join(', ') || 'Unspecified'}</span><span>Batches: {item.eligible_batches.join(', ') || 'Unspecified'}</span><span>Minimum CGPA: {item.minimum_cgpa ?? 'Unspecified'}</span><span>AI confidence: {item.ai_confidence ?? 'Not available'}</span></div>
    {item.missing_information.length > 0 && <p className="review-warning">Needs clarification: {item.missing_information.join(', ')}</p>}
    {(item.source_subject || item.source_sender) && <p className="review-source">Source: {item.source_subject || 'Email'}{item.source_sender ? ` · ${item.source_sender}` : ''}{item.source_link && <> · <a href={item.source_link} target="_blank" rel="noreferrer">Open original</a></>}</p>}
    {item.review_status === 'PENDING' && <div className="review-actions"><button className="secondary-button" onClick={() => { const company_name = window.prompt('Company name', item.company_name); if (!company_name) return; const application_deadline = window.prompt('Application deadline (ISO date/time)', item.application_deadline || ''); act('', { company_name, application_deadline: application_deadline || null }) }}>Edit details</button><button className="secondary-button" onClick={() => act('/reject', { reason: window.prompt('Reason for rejection') || 'Rejected by SPC' })}>Reject</button><button className="primary-button" onClick={() => act('/approve')}>Approve and publish</button></div>}
    {item.rejection_reason && <p className="review-warning">Rejected: {item.rejection_reason}</p>}
  </article>
}

function CompanyCard({ company, index, isSpc, onToggle, onEdit, onDelete }) {
  const colors = ['peach', 'sky', 'sage', 'lavender']
  const eventDate = new Date(company.date)
  const eventPassed = eventDate.getTime() <= Date.now()
  return <article id={`published-company-${company.id}`} className="company-card" style={{ '--delay': `${index * 70}ms` }}><div className={`company-logo ${colors[index % colors.length]}`}>{company.name?.slice(0, 2).toUpperCase()}</div><div className="company-card-body"><div className="card-topline"><span className="process-tag">{company.process?.replace('_', ' ')}</span><button className={company.interested ? 'heart-button saved' : 'heart-button'} title={eventPassed ? "Interest closed" : "Mark interest"} aria-label={eventPassed ? "Interest closed" : "Mark interest"} disabled={eventPassed} onClick={() => onToggle(company.id)}><Heart size={18} fill={company.interested ? 'currentColor' : 'none'} /></button></div><h3>{company.name}</h3><p className="company-meta"><MapPin size={15} />{company.location}</p><div className="card-bottom"><span><CalendarDays size={14} />{eventDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} · {eventDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</span>{isSpc && <div className="company-actions"><button className="edit-button" onClick={() => onEdit(company)}><Pencil size={14} /> Edit</button><button className="delete-button" onClick={() => onDelete(company)} aria-label={`Delete ${company.name}`} title={`Delete ${company.name}`}><Trash2 size={14} /> Delete</button></div>}</div></div></article>
}

export default App
