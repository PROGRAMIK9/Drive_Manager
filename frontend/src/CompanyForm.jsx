import { Check, X } from 'lucide-react'
import { useState } from 'react'

function toDateTimeLocal(value) {
  if (!value) return ''
  return value.slice(0, 16)
}

export default function CompanyForm({ company, onClose, onSave }) {
  const [form, setForm] = useState({
    name: company?.name || '',
    process: company?.process || 'online_assesment',
    location: company?.location || '',
    date: toDateTimeLocal(company?.date),
    year_of_passing: company?.year_of_passing || 2027,
    considered: company?.considered || false,
  })

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div><span className="section-kicker">SPC tools</span><h2>{company ? 'Edit opportunity' : 'Add opportunity'}</h2></div>
          <button className="icon-button" onClick={onClose}><X size={19} /></button>
        </div>
        <form onSubmit={(event) => { event.preventDefault(); onSave(form) }}>
          <label>Company name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Company name" /></label>
          <div className="form-columns">
            <label>Process<select value={form.process} onChange={(event) => setForm({ ...form, process: event.target.value })}><option value="online_assesment">Online assessment</option><option value="interview">Interview</option><option value="ppt">Presentation</option><option value="group_discussion">Group discussion</option><option value="pen_paper_test">Pen-and-paper test</option><option value="technical_assessment">Technical assessment</option><option value="send_mail">Send mail (SPC only)</option></select></label>
            <label>Event date and time<input required type="datetime-local" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
          </div>
          <label>Year of passing<select value={form.year_of_passing} onChange={(event) => setForm({ ...form, year_of_passing: Number(event.target.value) })}><option value={2027}>2027</option><option value={2028}>2028</option></select></label>
          <label>Location<input required value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="City or remote" /></label>
          <div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" type="submit"><Check size={17} />{company ? 'Save changes' : 'Publish opportunity'}</button></div>
        </form>
      </div>
    </div>
  )
}
