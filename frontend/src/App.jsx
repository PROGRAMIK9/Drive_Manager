import { useEffect, useRef, useState } from 'react'
import { Bell, BriefcaseBusiness, Building2, CalendarDays, CircleAlert, Download, Heart, LogOut, MapPin, Menu, PanelLeftClose, PanelLeftOpen, Pencil, Plus, Search, Sparkles, Trash2, Users, X, MailCheck, Send } from 'lucide-react'
import CompanyForm from './CompanyForm'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || ''

function readStoredUser() {
  try { return JSON.parse(localStorage.getItem('drive-manager-user') || 'null') } catch { return null }
}

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) },
  })
  if (!response.ok) {
    const responseBody = await response.text().catch(() => '')
    let error = {}
    try { error = responseBody ? JSON.parse(responseBody) : {} } catch { error = {} }
    const detail = Array.isArray(error.detail)
      ? error.detail.map((item) => item.msg || JSON.stringify(item)).join(', ')
      : typeof error.detail === 'string'
        ? error.detail
        : error.detail?.msg || responseBody.slice(0, 300) || `Request failed (${response.status})`
    throw new Error(detail)
  }
  return response.status === 204 ? null : response.json()
}

function App() {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(readStoredUser)
  const [authMode, setAuthMode] = useState('login')
  const [companies, setCompanies] = useState([])
  const [search, setSearch] = useState('')
  const [activeFilter, setActiveFilter] = useState('All opportunities')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingCompany, setEditingCompany] = useState(null)
  const [activeView, setActiveView] = useState('opportunities')
  const [users, setUsers] = useState([])
  const [interestSummary, setInterestSummary] = useState([])
  const [pendingOpportunities, setPendingOpportunities] = useState([])
  const [gmailStatus, setGmailStatus] = useState({ connected: false })
  const [gmailBusy, setGmailBusy] = useState(false)
  const [senderStatus, setSenderStatus] = useState({ connected: false })
  const [announcementConfig, setAnnouncementConfig] = useState(null)
  const [campaigns, setCampaigns] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [installPrompt, setInstallPrompt] = useState(null)
  const [selectedYear, setSelectedYear] = useState(() => {
    try { return Number(localStorage.getItem('drive-manager-year') || 2027) } catch { return 2027 }
  })
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
    if (activeView === 'announcements') {
      Promise.all([
        request('/api/admin/placement/announcements/config', { headers }),
        request('/api/integrations/gmail/sender/status', { headers }),
        request('/api/admin/placement/announcements/campaigns', { headers }),
      ]).then(([config, sender, history]) => {
        setAnnouncementConfig(config)
        setSenderStatus(sender)
        setCampaigns(history)
      }).catch((e) => setError(e.message))
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
    setError('')
    setStatusMessage('')
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
      if (action === 'sync') {
        const pending = await request('/api/admin/placement/pending/', { headers: { Authorization: `Bearer ${token}` } })
        setPendingOpportunities(pending)
        setStatusMessage(`Mailbox sync checked ${result.fetched} messages, queued ${result.placement_opportunities} placement opportunities for SPC review, and ignored ${result.ignored_sender} messages from outside RVCE.`)
      }
      const status = await request('/api/integrations/gmail/status', { headers: { Authorization: `Bearer ${token}` } })
      setGmailStatus(status)
    } catch (requestError) { setError(requestError.message) } finally { setGmailBusy(false) }
  }

  async function connectSender() {
    try {
      const authorization = await request('/api/integrations/gmail/sender/connect', { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      window.location.assign(authorization.authorization_url)
    } catch (e) { setError(e.message) }
  }

  async function disconnectSender() {
    try {
      await request('/api/integrations/gmail/sender/disconnect', { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
      setSenderStatus({ connected: false })
    } catch (e) { setError(e.message) }
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
            <button className={`nav-item ${activeView === 'announcements' ? 'active' : ''}`} onClick={() => selectView('announcements')} title="Send announcements"><Send size={18} /><span className="nav-label">Send announcements</span></button>
          </>}
        </nav>
        <div className="sidebar-spacer" />
        {installPrompt && <button className="sidebar-action install-action" onClick={installApp}><Download size={17} /><span>Install app</span></button>}
        <button className="sidebar-action signout-action" onClick={handleLogout}><LogOut size={17} /><span>Sign out</span></button>
        <div className="sidebar-footnote">Driveboard · Campus opportunity desk</div>
      </aside>
      <main className="main-content" id="opportunities">
        <header className="topbar"><div className="topbar-leading"><button className="nav-toggle" aria-label="Open navigation" title="Open navigation" onClick={() => { setSidebarOpen(true); setSidebarCollapsed(false) }}><Menu size={20} /></button><div className="eyebrow">{isSpc ? 'Coordinator workspace' : 'Your opportunity desk'}</div></div><div className="topbar-actions"><div className="notification-wrap" ref={notificationRef}><button className={`icon-button notification-button ${notificationsOpen ? 'selected' : ''}`} title="Saved opportunities and upcoming dates" aria-label={`Notifications${upcomingCount ? `, ${upcomingCount} upcoming` : ''}`} aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}><Bell size={19} />{upcomingCount > 0 && <span className="notification-badge">{upcomingCount}</span>}</button>{notificationsOpen && <section className="notification-panel" aria-label="Saved opportunities"><div className="notification-panel-header"><div><span className="section-kicker">Your board</span><h2>Saved opportunities</h2></div><button className="notification-close" onClick={() => setNotificationsOpen(false)} aria-label="Close notifications"><X size={17} /></button></div>{savedOpportunities.length ? <div className="notification-list">{savedOpportunities.map((company) => <article className="notification-item" key={company.id}><span className="notification-mark"><CalendarDays size={16} /></span><div><strong>{company.name}</strong><span>{company.location}</span><small>{new Date(company.date).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</small></div></article>)}</div> : <p className="notification-empty">Save an opportunity with the heart button and its date will show up here.</p>}</section>}</div></div></header>
        {error && <div className="error-banner"><CircleAlert size={18} />{error}<button onClick={() => setError('')}><X size={16} /></button></div>}
        {statusMessage && <div className="notice-banner" role="status"><MailCheck size={18} />{statusMessage}<button aria-label="Dismiss message" onClick={() => setStatusMessage('')}><X size={16} /></button></div>}
        {activeView === 'announcements' && isSpc ? <AnnouncementWorkspace token={token} config={announcementConfig} setConfig={setAnnouncementConfig} sender={senderStatus} onConnectSender={connectSender} onDisconnectSender={disconnectSender} campaigns={campaigns} setCampaigns={setCampaigns} companies={companies} onError={setError} onStatus={setStatusMessage} /> : activeView === 'email-review' && isSpc ? <><section className="section-heading"><div><span className="section-kicker">SPC tools · Gmail integration</span><h2>Placement email review</h2></div></section><article className="interest-panel gmail-settings"><div><strong>{gmailStatus.connected ? (gmailStatus.watch_expiration ? "Gmail connected · watch active" : "Gmail connected · starting watch") : "Gmail not connected"}</strong><span>{gmailStatus.email_address || "Mailbox: maaryamannp.mca25@rvce.edu.in"}</span><small>Last sync: {gmailStatus.last_sync_at ? new Date(gmailStatus.last_sync_at).toLocaleString() : "Pending first sync"} · Watch expires: {gmailStatus.watch_expiration ? new Date(gmailStatus.watch_expiration).toLocaleString() : "Starting automatically"}</small>{gmailStatus.last_error && <small className="review-warning">{gmailStatus.last_error}</small>}</div><div className="review-actions">{!gmailStatus.connected ? <button className="primary-button" disabled={gmailBusy} onClick={() => runGmailAction("connect")}>Connect Gmail</button> : <><button className="secondary-button" disabled={gmailBusy} onClick={() => runGmailAction("watch")}>Start / renew watch</button><button className="secondary-button" disabled={gmailBusy} onClick={() => runGmailAction("sync")}>Sync mailbox</button><button className="secondary-button" disabled={gmailBusy} onClick={() => runGmailAction("disconnect")}>Disconnect</button></>}</div></article><p className="review-intro">New inbox messages are checked automatically. Emails from @rvce.edu.in are classified and placement details are sent here for SPC review; nothing is published to students until an SPC approves it.</p>{pendingOpportunities.length ? <div className="interest-list">{pendingOpportunities.map((item) => <ReviewOpportunity key={item.id} item={item} token={token} onUpdate={(updated) => setPendingOpportunities((items) => items.map((current) => current.id === updated.id ? updated : current))} onError={(message) => setError(message)} onOpenMatch={openDuplicateMatch} />)}</div> : <div className="empty-state"><MailCheck size={30} /><strong>No pending opportunities</strong><span>New review items will be listed here.</span></div>}</> : activeView === 'users' && isSpc ? <><section className="section-heading"><div><span className="section-kicker">SPC tools</span><h2>People on Driveboard</h2></div></section><div className="management-list">{users.map((person) => <article className="management-row" key={person.id}><div className="user-avatar">{person.name.slice(0, 1).toUpperCase()}</div><div className="management-details"><strong>{person.name}</strong><span>{person.email}</span></div><span className={`role-badge ${person.role.toLowerCase()}`}>{person.role}</span><select aria-label={`Role for ${person.name}`} value={person.role} onChange={(event) => changeRole(person, event.target.value)}><option value="STUDENT">Student</option><option value="SPC">SPC coordinator</option></select><select aria-label={`Year of passing for ${person.name}`} value={person.year_of_passing || ''} onChange={(event) => changeUserYear(person, event.target.value)}><option value="">Unassigned</option><option value="2027">2027</option><option value="2028">2028</option></select></article>)}</div></> : activeView === 'interest' && isSpc ? <><section className="section-heading"><div><span className="section-kicker">SPC tools</span><h2>Interest by drive</h2></div></section><div className="interest-list">{interestSummary.map((drive) => <article className="interest-panel" key={drive.company_id}><div className="interest-heading"><div><span className="process-tag">{drive.process.replace('_', ' ')}</span><h3>{drive.company_name}</h3><span className="company-meta">{drive.location} · {new Date(drive.date).toLocaleDateString()}</span></div><span className="interest-count">{drive.interested_users.length} interested</span></div>{drive.interested_users.length ? <div className="interested-people">{drive.interested_users.map((person) => <span className="person-chip" key={person.id}>{person.name} <small>{person.email}</small></span>)}</div> : <p className="no-interest">No students have marked interest yet.</p>}</article>)}</div></> : <><section className="section-heading"><div><span className="section-kicker">Explore the board</span><h2>Open opportunities</h2></div>{isSpc && <button className="primary-button" onClick={() => { setEditingCompany(null); setShowForm(true) }}><Plus size={17} /> Add company</button>}</section></>}
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

function AnnouncementWorkspace({ token, config, setConfig, sender, onConnectSender, onDisconnectSender, campaigns, setCampaigns, companies, onError, onStatus }) {
  const headers = { Authorization: `Bearer ${token}` }
  const [listKey, setListKey] = useState('all_students')
  const [recipientText, setRecipientText] = useState('')
  const [companyId, setCompanyId] = useState('')
  const templateKey = 'placement_announcement'
  const [consentUrl, setConsentUrl] = useState('')
  const [extraLinks, setExtraLinks] = useState('')
  const [toText, setToText] = useState('')
  const [ccText, setCcText] = useState('')
  const [busy, setBusy] = useState(false)
  const [files, setFiles] = useState([])
  const [recipients, setRecipients] = useState([])
  const [signature, setSignature] = useState('')
  const [draft, setDraft] = useState(null)
  const [sourceBody, setSourceBody] = useState('')
  const [additionalDetails, setAdditionalDetails] = useState('{}')
  const [includeOriginalBody, setIncludeOriginalBody] = useState(false)
  const lists = config?.recipient_lists || []
  const selectedList = lists.find((item) => item.list_key === listKey)
  const selectedCompany = companies.find((item) => String(item.id) === String(companyId))
  const templates = config?.templates || {}
  const currentTemplate = templates[templateKey] || {}
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')

  useEffect(() => {
    if (!companyId) { setSourceBody(''); setAdditionalDetails('{}'); return }
    request('/api/admin/placement/pending/?status=APPROVED', { headers }).then((items) => {
      const source = items.find((item) => String(item.published_company_id) === String(companyId))
      setSourceBody(source?.source_body || '')
      setAdditionalDetails(JSON.stringify(source?.extracted_details?.additional_details || {}, null, 2))
    }).catch((e) => onError(e.message))
  }, [companyId])

  useEffect(() => {
    if (!selectedList) return
    request(`/api/admin/placement/announcements/lists/${selectedList.id}/recipients`, { headers })
      .then(setRecipients).catch((e) => onError(e.message))
  }, [selectedList?.id])
  useEffect(() => {
    if (sender.signature_text !== undefined) setSignature(sender.signature_text)
  }, [sender.signature_text])
  useEffect(() => {
    if (selectedCompany && currentTemplate.subject) {
      setSubject(currentTemplate.subject.replaceAll('{company_name}', selectedCompany.name).replaceAll('{role}', selectedCompany.process.replaceAll('_', ' ')))
      const lead = `${selectedCompany.name} is recruiting students. The details are as follows:`
      setBody(`Hello everyone,\n\n${lead}\n\n**Company:** ${selectedCompany.name}\n**Profile offered:** ${selectedCompany.process.replaceAll('_', ' ')}\n\nInterested students are required to fill the consent form by the stated deadline.`)
    }
  }, [companyId, templateKey, config?.templates, selectedCompany?.name, selectedCompany?.process, currentTemplate.body, currentTemplate.subject])

  function splitEmails(value) { return value.split(/[\s,;]+/).map((email) => email.trim()).filter(Boolean) }
  async function saveConfig() {
    setBusy(true)
    try {
      const updated = await request('/api/admin/placement/announcements/config', { method: 'PUT', headers, body: JSON.stringify({
        placement_director_email: config.placement_director_email || null,
        co_spc_emails: config.co_spc_emails || [],
        staff_coordinator_email: config.staff_coordinator_email || null,
        templates,
      }) })
      setConfig(updated)
      onStatus('Announcement recipients and templates saved.')
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  async function importRecipients() {
    if (!selectedList || !recipientText.trim()) return
    setBusy(true)
    try {
      const result = await request(`/api/admin/placement/announcements/lists/${selectedList.id}/import`, { method: 'POST', headers, body: JSON.stringify({ content: recipientText }) })
      setRecipientText('')
      const updated = await request(`/api/admin/placement/announcements/lists/${selectedList.id}/recipients`, { headers })
      setRecipients(updated)
      const config = await request('/api/admin/placement/announcements/config', { headers }); setConfig(config)
      onStatus(`Recipient list updated: ${result.added} added, ${result.reactivated} reactivated, ${result.duplicates_removed} duplicates skipped.`)
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  async function refreshRecipients() {
    if (!selectedList) return
    const updated = await request(`/api/admin/placement/announcements/lists/${selectedList.id}/recipients`, { headers })
    setRecipients(updated)
    const nextConfig = await request('/api/admin/placement/announcements/config', { headers })
    setConfig(nextConfig)
  }
  async function removeRecipient(recipient) {
    setBusy(true)
    try {
      await request(`/api/admin/placement/announcements/recipients/${recipient.id}`, { method: 'DELETE', headers })
      await refreshRecipients()
      onStatus(`${recipient.email} removed from the student list.`)
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  async function clearRecipientList() {
    if (!selectedList || !window.confirm(`Permanently remove every address from ${selectedList.name}? This does not change sent campaign history.`)) return
    setBusy(true)
    try {
      const result = await request(`/api/admin/placement/announcements/lists/${selectedList.id}/recipients`, { method: 'DELETE', headers })
      await refreshRecipients()
      onStatus(`Cleared ${result.deleted} addresses from ${selectedList.name}.`)
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  async function setRecipientActive(recipient, active) {
    setBusy(true)
    try {
      await request(`/api/admin/placement/announcements/recipients/${recipient.id}?active=${active}`, { method: 'PATCH', headers })
      await refreshRecipients()
      onStatus(`${recipient.email} ${active ? 'restored to' : 'removed from'} the active student list.`)
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  async function saveSignature() {
    try {
      await request('/api/integrations/gmail/sender/signature', { method: 'PUT', headers, body: JSON.stringify({ signature_text: signature }) })
      onStatus('Your sender signature was saved.')
    } catch (e) { onError(e.message) }
  }
  async function uploadFiles(event) {
    const chosen = [...event.target.files]
    for (const file of chosen) {
      const form = new FormData(); form.append('file', file)
      try { const saved = await request('/api/admin/placement/announcements/files', { method: 'POST', headers, body: form }); setFiles((current) => [...current, { kind: 'upload', file_id: saved.id, filename: saved.filename }]) }
      catch (e) { onError(e.message) }
    }
    event.target.value = ''
  }
  async function createDraft() {
    if (!selectedCompany || !selectedList || !consentUrl.trim()) { onError('Choose a published opportunity, recipient list, and Google Form consent link.'); return }
    setBusy(true)
    try {
      const parsedLinks = extraLinks.split('\n').map((line) => line.trim()).filter(Boolean).map((line) => { const [label, url] = line.split('|').map((part) => part.trim()); return { label: label || 'More information', url: url || label } })
      let details
      try { details = additionalDetails.trim() ? JSON.parse(additionalDetails) : {} } catch { throw new Error('Additional details must be valid JSON.') }
      if (!details || typeof details !== 'object' || Array.isArray(details)) throw new Error('Additional details must be a JSON object.')
      if (includeOriginalBody && sourceBody.trim()) details.original_email_body = sourceBody
      const created = await request('/api/admin/placement/announcements/campaigns', { method: 'POST', headers, body: JSON.stringify({
        company_id: selectedCompany.id, recipient_list_id: selectedList.id, template_key: templateKey, consent_form_url: consentUrl,
        subject, body, include_signature: true, to_emails: toText.trim() ? splitEmails(toText) : undefined, cc_emails: ccText.trim() ? splitEmails(ccText) : undefined,
        links: parsedLinks, attachments: files, additional_details: details, request_key: crypto.randomUUID(),
      }) })
      setDraft(created)
      setCampaigns((current) => [created, ...current.filter((item) => item.id !== created.id)])
      onStatus('Draft saved. Review the recipients and message preview before sending.')
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  async function sendDraft() {
    if (!draft) return
    if (!window.confirm(`Send this announcement to ${draft.bcc_count} students using ${draft.sender_email}?`)) return
    setBusy(true)
    try {
      const sent = await request(`/api/admin/placement/announcements/campaigns/${draft.id}/send`, { method: 'POST', headers, body: JSON.stringify({ request_key: draft.request_key }) })
      setDraft(sent); setCampaigns((current) => [sent, ...current.filter((item) => item.id !== sent.id)])
      onStatus(`Announcement sending finished: ${sent.status}.`)
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }
  return <>
    <section className="section-heading"><div><span className="section-kicker">SPC tools · student announcements</span><h2>Send placement announcements</h2></div></section>
    <article className="interest-panel announcement-panel"><div><strong>{sender.connected ? `Sending account connected · ${sender.email_address}` : 'Connect your own sending account'}</strong><span>This account sends announcements. The separate placement inbox stays connected for email review.</span></div>{sender.connected ? <button className="secondary-button" onClick={onDisconnectSender}>Disconnect sender</button> : <button className="primary-button" onClick={onConnectSender}>Connect Gmail sender</button>}</article>
    {sender.connected && <>
      <article className="interest-panel announcement-panel"><div className="announcement-form"><h3>Automatic signature</h3><p>Gmail API sends do not append the signature from Gmail’s web compose settings. Add the text here; it appears in the preview and message.</p><textarea value={signature} onChange={(e) => setSignature(e.target.value)} placeholder={'Regards,\nYour name\nStudent Placement Coordinator'} rows={4} /></div><button className="secondary-button" onClick={saveSignature}>Save signature</button></article>
      <div className="announcement-grid">
        <details className="interest-panel announcement-disclosure">
          <summary><span><strong>Recipients and announcement</strong><small>Placement director, CC list, and default message</small></span></summary>
          <div className="announcement-form">
            <label>Placement director email<input value={config?.placement_director_email || ''} onChange={(e) => setConfig({ ...config, placement_director_email: e.target.value })} placeholder="director-mca@rvce.edu.in" /></label>
            <label>CC emails<input value={(config?.co_spc_emails || []).join(', ')} onChange={(e) => setConfig({ ...config, co_spc_emails: splitEmails(e.target.value) })} placeholder="Co-SPC addresses, comma separated" /></label>
            <label>Staff coordinator email<input value={config?.staff_coordinator_email || ''} onChange={(e) => setConfig({ ...config, staff_coordinator_email: e.target.value })} placeholder="Coordinator address" /></label>
            <label>Subject<input value={currentTemplate.subject || ''} onChange={(e) => setConfig({ ...config, templates: { ...templates, [templateKey]: { ...currentTemplate, subject: e.target.value } } })} /></label>
            <label>Message guidance<textarea rows={5} value={currentTemplate.body || ''} onChange={(e) => setConfig({ ...config, templates: { ...templates, [templateKey]: { ...currentTemplate, body: e.target.value } } })} /></label>
            <button className="secondary-button" disabled={busy} onClick={saveConfig}>Save recipients and templates</button>
          </div>
        </details>
        <details className="interest-panel announcement-disclosure">
          <summary><span><strong>Student list</strong><small>{selectedList?.active_count || 0} active addresses · choose to import, remove, or clear</small></span></summary>
          <div className="announcement-form">
            <label>List<select value={listKey} onChange={(e) => setListKey(e.target.value)}>{lists.map((item) => <option key={item.id} value={item.list_key}>{item.name} · {item.active_count} active</option>)}</select></label>
            <p>Import addresses to add or restore students. Removing a student takes them out of future sends.</p>
            <textarea rows={5} value={recipientText} onChange={(e) => setRecipientText(e.target.value)} placeholder="Paste student email addresses here" />
            <div className="recipient-management-actions"><button className="secondary-button" disabled={busy || !recipientText.trim()} onClick={importRecipients}>Import addresses</button><button className="danger-button" disabled={busy || recipients.length === 0} onClick={clearRecipientList}>Clear list</button></div>
            <div className="recipient-preview">{recipients.filter((item) => item.active).length} active addresses</div>
            <div className="recipient-list" aria-label="Students in the selected list">
              {recipients.length === 0 ? <p>No addresses in this list yet.</p> : recipients.map((recipient) => <div className={`recipient-row${recipient.active ? '' : ' is-inactive'}`} key={recipient.id}><span>{recipient.name || recipient.email}<small>{recipient.name ? recipient.email : ''}{!recipient.active ? ' · removed' : ''}</small></span>{recipient.active ? <button className="recipient-remove" disabled={busy} onClick={() => removeRecipient(recipient)} aria-label={`Delete ${recipient.email}`}><Trash2 size={15} /> Remove</button> : <button className="recipient-restore" disabled={busy} onClick={() => setRecipientActive(recipient, true)}>Restore</button>}</div>)}
            </div>
          </div>
        </details>
      </div>
      <article className="interest-panel announcement-form campaign-form"><h3>Compose announcement</h3><p>Start with the placement email facts, then edit the complete message. Extra details are saved with the campaign even when they do not fit a standard field.</p><div className="form-columns"><label>Published opportunity<select value={companyId} onChange={(e) => setCompanyId(e.target.value)}><option value="">Choose company</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.name} · {company.process.replaceAll('_', ' ')}</option>)}</select></label><label>Distribution list<select value={listKey} onChange={(e) => setListKey(e.target.value)}>{lists.map((item) => <option key={item.id} value={item.list_key}>{item.name} · {item.active_count} active</option>)}</select></label><label>Consent Google Form URL<input value={consentUrl} onChange={(e) => setConsentUrl(e.target.value)} placeholder="https://docs.google.com/forms/..." /></label><label>To<input value={toText || config?.placement_director_email || ''} onChange={(e) => setToText(e.target.value)} /></label><label>CC<input value={ccText || [...(config?.co_spc_emails || []), config?.staff_coordinator_email].filter(Boolean).join(', ')} onChange={(e) => setCcText(e.target.value)} /></label><label>Subject<input value={subject} onChange={(e) => setSubject(e.target.value)} /></label></div><label>Message<textarea rows={7} value={body} onChange={(e) => setBody(e.target.value)} /></label><label>Additional details (JSON)<small>Examples: vacancies, exact address, rounds, PBC/FTE conditions, work location details.</small><textarea rows={6} value={additionalDetails} onChange={(e) => setAdditionalDetails(e.target.value)} /></label>{sourceBody && <><label className="source-email-toggle"><input type="checkbox" checked={includeOriginalBody} onChange={(e) => setIncludeOriginalBody(e.target.checked)} /> Include original placement email in saved campaign details</label><details className="source-email-body"><summary>View original placement email</summary><pre>{sourceBody}</pre></details></>}<label>Additional links <small>One per line: Label | https://…</small><textarea rows={3} value={extraLinks} onChange={(e) => setExtraLinks(e.target.value)} placeholder="Job description | https://…" /></label><label>Attachments (PDF, DOC, DOCX, XLSX; up to 8 MB each)<input type="file" accept=".pdf,.doc,.docx,.xlsx" multiple onChange={uploadFiles} /></label>{files.map((file, index) => <div className="file-chip" key={`${file.filename}-${index}`}>{file.filename}<button onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}>Remove</button></div>)}<div className="review-actions"><button className="primary-button" disabled={busy} onClick={createDraft}>Save draft and preview</button>{draft && <button className="primary-button" disabled={busy || draft.status !== 'DRAFT'} onClick={sendDraft}>Send announcement</button>}</div>
      {draft && <div className="campaign-preview"><span className="section-kicker">Preview · {draft.status}</span><h3>{draft.subject}</h3><p>From: {draft.sender_email} · To: {draft.to_emails.join(', ')} · CC: {draft.cc_emails.join(', ') || 'None'} · BCC: {draft.bcc_count} students</p><pre>{draft.body}{draft.include_signature && draft.signature_text ? `\n\n${draft.signature_text}` : ''}{Object.entries(draft.additional_details || {}).filter(([key]) => key !== 'original_email_body').map(([key, value]) => `\n\n${key.replaceAll('_', ' ')}: ${typeof value === 'string' ? value : JSON.stringify(value)}`).join('')}\n\nConsent form: {draft.consent_form_url}{(draft.links || []).map((link) => `\n${link.label}: ${link.url}`).join('')}</pre><p>Attachments: {draft.attachment_names.join(', ') || 'None'}</p></div>}</article>
      <section className="interest-list"><h3>Campaign history</h3>{campaigns.map((campaign) => <article className="interest-panel campaign-row" key={campaign.id}><div><strong>{campaign.subject}</strong><span>{campaign.status} · {campaign.sender_email} · {campaign.bcc_count} BCC recipients</span><small>{new Date(campaign.created_at).toLocaleString()}</small>{campaign.error_details && <small className="review-warning">{campaign.error_details}</small>}</div></article>)}</section>
    </>}
  </>
}

function ReviewOpportunity({ item, token, onUpdate, onError, onOpenMatch }) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  async function act(action, payload) {
    try {
      const updated = await request(`/api/admin/placement/pending/${item.id}${action}`, {
        method: action ? 'POST' : 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      })
      onUpdate(updated)
      return true
    } catch (error) { onError(error.message); return false }
  }
  async function saveDetails(payload) {
    setSaving(true)
    const saved = await act('', payload)
    setSaving(false)
    if (saved) setEditing(false)
  }
  return <>
  <article id={`pending-opportunity-${item.id}`} className="interest-panel review-card">
    <div className="interest-heading"><div><span className={`review-status ${item.eligibility_status.toLowerCase()}`}>{item.eligibility_status.replaceAll('_', ' ')}</span><h3>{item.company_name}{item.job_title ? ` · ${item.job_title}` : ''}</h3><span className="company-meta">{item.opportunity_type || 'Placement opportunity'} · {item.location || 'Location not specified'}</span></div><span className="role-badge">{item.review_status}</span></div>
    {item.possible_duplicates?.length > 0 && <div className="duplicate-warning" role="note"><strong>Possible duplicate</strong><span>Same normalized company, process, and date found:</span><ul>{item.possible_duplicates.map((match) => <li key={`${match.record_type}-${match.record_id}-${match.process}-${match.event_date}`}><button type="button" onClick={() => onOpenMatch(match)}>Open {match.record_type === 'PENDING' ? 'pending review' : 'published company'} #{match.record_id}</button><span>{match.company_name} · {match.process.replaceAll('_', ' ')} · {new Date(match.event_date).toLocaleDateString()}</span></li>)}</ul></div>}
    {item.description && <p className="review-copy">{item.description}</p>}
    <div className="review-facts"><span>Department submission: {item.department_submission_date ? new Date(item.department_submission_date).toLocaleString() : 'Not specified'}</span><span>OA: {item.assessment_date ? new Date(item.assessment_date).toLocaleString() : 'Not specified'}</span><span>GD: {item.group_discussion_date ? new Date(item.group_discussion_date).toLocaleString() : 'Not specified'}</span><span>Interview dates: {item.interview_dates?.length ? item.interview_dates.map(formatInterviewDate).join(', ') : item.interview_date ? new Date(item.interview_date).toLocaleString() : 'Not specified'}</span><span>Application deadline: {item.application_deadline ? new Date(item.application_deadline).toLocaleString() : 'Not specified'}</span><span>Courses: {item.eligible_courses.join(', ') || 'Unspecified'}</span><span>Batches: {item.eligible_batches.join(', ') || 'Unspecified'}</span><span>Minimum CGPA: {item.minimum_cgpa ?? 'Unspecified'}</span><span>AI confidence: {item.ai_confidence ?? 'Not available'}</span></div>
    {item.missing_information.length > 0 && <p className="review-warning">Needs clarification: {item.missing_information.join(', ')}</p>}
    {(item.source_subject || item.source_sender) && <p className="review-source">Source: {item.source_subject || 'Email'}{item.source_sender ? ` · ${item.source_sender}` : ''}{item.source_link && <> · <a href={item.source_link} target="_blank" rel="noreferrer">Open original</a></>}</p>}
    {item.review_status === 'PENDING' && <div className="review-actions"><button className="secondary-button" onClick={() => setEditing(true)}>Edit details</button><button className="secondary-button" onClick={() => act('/reject', { reason: window.prompt('Reason for rejection') || 'Rejected by SPC' })}>Reject</button><button className="primary-button" onClick={() => act('/approve')}>Approve and publish</button></div>}
    {item.rejection_reason && <p className="review-warning">Rejected: {item.rejection_reason}</p>}
  </article>
  {editing && <ReviewEditModal item={item} saving={saving} onClose={() => setEditing(false)} onSave={saveDetails} />}
  </>
}

function toLocalDateTime(value) {
  if (!value) return ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value}T00:00`
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function localDateTimeToIso(value) {
  return value ? new Date(value).toISOString() : null
}

function formatInterviewDate(value) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return new Date(year, month - 1, day).toLocaleDateString()
  }
  return new Date(value).toLocaleString()
}

function toInterviewInput(value) {
  if (!value) return { date: '', time: '' }
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return { date: value, time: '' }
  const local = toLocalDateTime(value)
  return { date: local.slice(0, 10), time: local.slice(11, 16) }
}

function ReviewEditModal({ item, saving, onClose, onSave }) {
  const [form, setForm] = useState(() => ({
    company_name: item.company_name || '',
    job_title: item.job_title || '',
    location: item.location || '',
    application_deadline: toLocalDateTime(item.application_deadline),
    department_submission_date: toLocalDateTime(item.department_submission_date),
    assessment_date: toLocalDateTime(item.assessment_date),
    group_discussion_date: toLocalDateTime(item.group_discussion_date),
    interview_dates: (item.interview_dates?.length ? item.interview_dates : item.interview_date ? [item.interview_date] : []).map(toInterviewInput),
  }))
  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }))

  function submit(event) {
    event.preventDefault()
    const interviewSlots = form.interview_dates.filter((slot) => slot.date).map((slot) => ({
      date: slot.date,
      value: slot.time ? localDateTimeToIso(`${slot.date}T${slot.time}`) : slot.date,
      eventDate: localDateTimeToIso(`${slot.date}T${slot.time || '00:00'}`),
    })).sort((a, b) => a.date.localeCompare(b.date) || a.value.localeCompare(b.value))
    const interviewDates = interviewSlots.map((slot) => slot.value)
    onSave({
      company_name: form.company_name.trim(),
      job_title: form.job_title.trim() || null,
      location: form.location.trim() || null,
      application_deadline: localDateTimeToIso(form.application_deadline),
      department_submission_date: localDateTimeToIso(form.department_submission_date),
      assessment_date: localDateTimeToIso(form.assessment_date),
      group_discussion_date: localDateTimeToIso(form.group_discussion_date),
      interview_date: interviewSlots[0]?.eventDate || null,
      interview_dates: interviewDates,
    })
  }

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !saving && onClose()}>
    <section className="modal review-edit-modal" role="dialog" aria-modal="true" aria-labelledby={`review-edit-title-${item.id}`}>
      <div className="modal-header"><div><span className="section-kicker">SPC review</span><h2 id={`review-edit-title-${item.id}`}>Edit opportunity details</h2></div><button className="icon-button" type="button" aria-label="Close edit form" disabled={saving} onClick={onClose}><X size={19} /></button></div>
      <form onSubmit={submit}>
        <div className="review-edit-grid">
          <label>Company name<input required value={form.company_name} onChange={(event) => setField('company_name', event.target.value)} /></label>
          <label>Role / position<input value={form.job_title} onChange={(event) => setField('job_title', event.target.value)} /></label>
          <label>Location<input value={form.location} onChange={(event) => setField('location', event.target.value)} /></label>
          <label>Application deadline<input type="datetime-local" value={form.application_deadline} onChange={(event) => setField('application_deadline', event.target.value)} /></label>
          <label>SPC database submission date<input type="datetime-local" value={form.department_submission_date} onChange={(event) => setField('department_submission_date', event.target.value)} /></label>
          <label>Online assessment (OA)<input type="datetime-local" value={form.assessment_date} onChange={(event) => setField('assessment_date', event.target.value)} /></label>
          <label>Group discussion (GD)<input type="datetime-local" value={form.group_discussion_date} onChange={(event) => setField('group_discussion_date', event.target.value)} /></label>
        </div>
        <div className="interview-date-editor"><div className="interview-date-heading"><strong>Interview dates and times</strong><button type="button" className="text-button" onClick={() => setField('interview_dates', [...form.interview_dates, ''])}><Plus size={15} /> Add date</button></div>
          {form.interview_dates.map((slot, index) => <div className="interview-date-row" key={index}><label>Interview {index + 1} date<input type="date" value={slot.date} onChange={(event) => setField('interview_dates', form.interview_dates.map((current, row) => row === index ? { ...current, date: event.target.value } : current))} /></label><label>Time (optional)<input type="time" value={slot.time} onChange={(event) => setField('interview_dates', form.interview_dates.map((current, row) => row === index ? { ...current, time: event.target.value } : current))} /></label><button type="button" className="interview-date-remove" aria-label={`Remove interview ${index + 1}`} disabled={saving} onClick={() => setField('interview_dates', form.interview_dates.filter((_, row) => row !== index))}><X size={17} /></button></div>)}
        </div>
        <div className="modal-actions"><button type="button" className="secondary-button" disabled={saving} onClick={onClose}>Cancel</button><button className="primary-button" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save details'}</button></div>
      </form>
    </section>
  </div>
}

function CompanyCard({ company, index, isSpc, onToggle, onEdit, onDelete }) {
  const colors = ['peach', 'sky', 'sage', 'lavender']
  const eventDate = new Date(company.date)
  const eventPassed = eventDate.getTime() <= Date.now()
  return <article id={`published-company-${company.id}`} className="company-card" style={{ '--delay': `${index * 70}ms` }}><div className={`company-logo ${colors[index % colors.length]}`}>{company.name?.slice(0, 2).toUpperCase()}</div><div className="company-card-body"><div className="card-topline"><span className="process-tag">{company.process?.replace('_', ' ')}</span><button className={company.interested ? 'heart-button saved' : 'heart-button'} title={eventPassed ? "Interest closed" : "Mark interest"} aria-label={eventPassed ? "Interest closed" : "Mark interest"} disabled={eventPassed} onClick={() => onToggle(company.id)}><Heart size={18} fill={company.interested ? 'currentColor' : 'none'} /></button></div><h3>{company.name}</h3><p className="company-meta"><MapPin size={15} />{company.location}</p><div className="card-bottom"><span><CalendarDays size={14} />{eventDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} · {eventDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</span>{isSpc && <div className="company-actions"><button className="edit-button" onClick={() => onEdit(company)}><Pencil size={14} /> Edit</button><button className="delete-button" onClick={() => onDelete(company)} aria-label={`Delete ${company.name}`} title={`Delete ${company.name}`}><Trash2 size={14} /> Delete</button></div>}</div></div></article>
}

export default App
