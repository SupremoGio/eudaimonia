// EUDAIMONIA — All Screens
// hooks and C declared in eu-components.jsx (bundled before this file)

// ═══════════════════════════════════════════════════════════
// ICONS — hand-authored line icons (Lucide-style), self-contained
// so the dashboard has no external icon CDN dependency to fail on.
// ═══════════════════════════════════════════════════════════
function EuIcon({ children, size = 16, viewBox = '0 0 24 24', fill = 'none', style, ...rest }) {
  return (
    <svg width={size} height={size} viewBox={viewBox} fill={fill} stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
      style={{ display:'block', flexShrink:0, ...style }} {...rest}>
      {children}
    </svg>
  );
}
const IconCommand = p => (
  <EuIcon {...p}>
    <rect x="4" y="4" width="16" height="16" rx="4"/>
    <circle cx="9" cy="9" r="1.4" fill="currentColor" stroke="none"/>
    <circle cx="15" cy="9" r="1.4" fill="currentColor" stroke="none"/>
    <circle cx="9" cy="15" r="1.4" fill="currentColor" stroke="none"/>
    <circle cx="15" cy="15" r="1.4" fill="currentColor" stroke="none"/>
  </EuIcon>
);
const IconTrophy = p => (
  <EuIcon {...p}>
    <path d="M8 4h8v5a4 4 0 0 1-8 0V4z"/>
    <path d="M8 5H5a2 2 0 0 0 0 4h2"/>
    <path d="M16 5h3a2 2 0 0 1 0 4h-2"/>
    <line x1="12" y1="13" x2="12" y2="17"/>
    <line x1="9" y1="20" x2="15" y2="20"/>
    <line x1="12" y1="17" x2="12" y2="20"/>
  </EuIcon>
);
const IconMountain = p => (
  <EuIcon {...p}><path d="M3 20 9 8 13 15 17 9 21 20z"/></EuIcon>
);
const IconSwords = p => (
  <EuIcon {...p}>
    <line x1="5" y1="19" x2="19" y2="5"/>
    <line x1="19" y1="19" x2="5" y2="5"/>
    <line x1="15" y1="9" x2="17" y2="7"/>
    <line x1="9" y1="9" x2="7" y2="7"/>
  </EuIcon>
);
const IconMedal = p => (
  <EuIcon {...p}>
    <circle cx="12" cy="15" r="5"/>
    <path d="M9 11 6 3M15 11 18 3"/>
    <path d="M9.5 15.5l1.3 1.5 2.2-3"/>
  </EuIcon>
);
const IconGem = p => (
  <EuIcon {...p}>
    <path d="M6 3h12l4 6-10 12L2 9z"/>
    <path d="M2 9h20M9 3l3 6-3 12M15 3l-3 6 3 12"/>
  </EuIcon>
);
const IconZap = p => (
  <EuIcon {...p} fill="currentColor">
    <polygon points="13,2 3,14 11,14 9,22 21,10 13,10" stroke="none"/>
  </EuIcon>
);
const IconRefreshCw = p => (
  <EuIcon {...p}>
    <path d="M21 12a9 9 0 0 1-15.5 6.5L3 16"/>
    <polyline points="3 21 3 16 8 16"/>
    <path d="M3 12a9 9 0 0 1 15.5-6.5L21 8"/>
    <polyline points="21 3 21 8 16 8"/>
  </EuIcon>
);
const IconBell = p => (
  <EuIcon {...p}>
    <path d="M12 3a5 5 0 0 0-5 5v3.5c0 1-.4 2-1.2 2.8L4 16h16l-1.8-1.7c-.8-.8-1.2-1.8-1.2-2.8V8a5 5 0 0 0-5-5z"/>
    <path d="M9.5 19a2.5 2.5 0 0 0 5 0"/>
  </EuIcon>
);
const IconCheckSquare = p => (
  <EuIcon {...p}>
    <rect x="3" y="3" width="18" height="18" rx="3"/>
    <polyline points="7 12 10.5 15.5 17 8.5"/>
  </EuIcon>
);
const IconShoppingBag = p => (
  <EuIcon {...p}>
    <path d="M6 8h12l-1 12H7z"/>
    <path d="M9 8V6a3 3 0 0 1 6 0v2"/>
  </EuIcon>
);
const IconCheck = p => (
  <EuIcon {...p}><polyline points="4 12 9.5 17.5 20 6"/></EuIcon>
);
const IconGlobe = p => (
  <EuIcon {...p}>
    <circle cx="12" cy="12" r="9"/>
    <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/>
  </EuIcon>
);
const IconTerminal = p => (
  <EuIcon {...p}>
    <rect x="2" y="4" width="20" height="16" rx="2"/>
    <polyline points="6 9 10 12 6 15"/>
    <line x1="12" y1="15" x2="17" y2="15"/>
  </EuIcon>
);
const IconMusic = p => (
  <EuIcon {...p}>
    <circle cx="6" cy="18" r="2.5"/>
    <circle cx="17" cy="16" r="2.5"/>
    <path d="M8.5 18V6l11-2v12"/>
  </EuIcon>
);
const IconShieldCheck = p => (
  <EuIcon {...p}>
    <path d="M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6z"/>
    <polyline points="9 12 11 14 15 9.5"/>
  </EuIcon>
);
const IconWallet = p => (
  <EuIcon {...p}>
    <path d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
    <path d="M16 12h3v3h-3a1.5 1.5 0 0 1 0-3z"/>
  </EuIcon>
);
const IconClipboardCheck = p => (
  <EuIcon {...p}>
    <rect x="5" y="4" width="14" height="17" rx="2"/>
    <rect x="9" y="2" width="6" height="4" rx="1"/>
    <polyline points="9 13 11 15 15 10.5"/>
  </EuIcon>
);
const IconBookOpen = p => (
  <EuIcon {...p}>
    <path d="M12 6c-2-1.5-4.5-2-7-2v13c2.5 0 5 .5 7 2 2-1.5 4.5-2 7-2V4c-2.5 0-5 .5-7 2z"/>
    <line x1="12" y1="6" x2="12" y2="19"/>
  </EuIcon>
);
const IconFutbol = p => (
  <EuIcon {...p}>
    <circle cx="12" cy="12" r="9"/>
    <path d="M12 7.5l3 2.2-1.1 3.6h-3.8L9 9.7z"/>
    <path d="M12 3v4.5M12 20.5V16M4.2 9l3.5 1.2M16.3 10.2L19.8 9M5.8 17l2.9-3.1M15.3 13.9l2.9 3.1"/>
  </EuIcon>
);
const IconArrowRight = p => (
  <EuIcon {...p}>
    <line x1="4" y1="12" x2="18" y2="12"/>
    <polyline points="12 6 18 12 12 18"/>
  </EuIcon>
);

const MODULE_ICONS = {
  hegemonikon: IconShieldCheck, oikonomia: IconWallet, ataraxia: IconClipboardCheck,
  paideia: IconBookOpen, cosmopolitismo: IconGlobe, logoi: IconTerminal, eurythmia: IconMusic,
};
const DEADLINE_TYPE_ICON  = { reminder: IconBell, task: IconCheckSquare, wishlist: IconShoppingBag, partido: IconFutbol };
const DEADLINE_TYPE_LABEL = { reminder: 'recordatorio', task: 'tarea gtd', wishlist: 'wishlist', partido: 'partido' };
const DEADLINE_PAL = {
  red:    { text:'#f87171', bg:'rgba(239,68,68,0.09)',  border:'#ef4444', pill:'rgba(239,68,68,0.20)'  },
  amber:  { text:'#fbbf24', bg:'rgba(245,158,11,0.09)', border:'#f59e0b', pill:'rgba(245,158,11,0.20)' },
  yellow: { text:'#fde047', bg:'rgba(234,179,8,0.07)',  border:'#eab308', pill:'rgba(234,179,8,0.18)'  },
  green:  { text:'#34d399', bg:'rgba(16,185,129,0.07)', border:'#10b981', pill:'rgba(16,185,129,0.18)' },
};

// ─── Shared deadlines/reminders state — one source of truth for the ─────────
// sidebar Deadline Radar and the topbar notification bell.
function useDeadlines() {
  const initial = (window.EU._server || {}).deadlines || [];
  const [deadlines, setDeadlines] = useState(initial);
  const [checking, setChecking] = useState({});

  async function handleCheck(dl) {
    if (checking[dl.id]) return;
    // Solo reminders/tareas GTD se "marcan cumplidas" con un click — otros
    // tipos (ej. partidos) tienen su propio flujo, ver DeadlineItemCard.
    if (dl.type !== 'task' && dl.type !== 'reminder') return;
    setChecking(prev => ({...prev, [dl.id]: true}));
    const url = dl.type === 'task'
      ? `/gtd/api/task/${dl.id}/complete`
      : `/perfil/api/reminder/${dl.id}/done`;
    try {
      const res = await fetch(url, {method:'POST'});
      const j = await res.json();
      if (j.ok) {
        setDeadlines(prev => prev.filter(d => !(d.id === dl.id && d.type === dl.type)));
      }
    } catch(e) {}
    setChecking(prev => ({...prev, [dl.id]: false}));
  }

  return { deadlines, checking, handleCheck };
}

// ─── One deadline/reminder card — reused by the sidebar radar and the ──────
// topbar notification dropdown.
function DeadlineItemCard({ dl, isChecking, onCheck }) {
  const p = DEADLINE_PAL[dl.level] || DEADLINE_PAL.green;
  const urgent = dl.level === 'red';
  const sublabel = dl.days > 0 ? 'DÍAS' : dl.days === 0 ? 'DEADLINE' : 'EXPIRADO';
  const TypeIcon = DEADLINE_TYPE_ICON[dl.type] || IconBell;

  return (
    <div style={{
      display:'flex',alignItems:'stretch',
      borderRadius:14,overflow:'hidden',
      border:'1px solid rgba(255,255,255,0.05)',
      background:p.bg,
      boxShadow:'0 2px 14px rgba(0,0,0,0.32)',
      opacity: isChecking ? 0.5 : 1,
      transition:'opacity 0.2s',
    }}>
      {/* Barra lateral */}
      <div style={{
        width:3,flexShrink:0,background:p.border,
        boxShadow: urgent ? `0 0 9px ${p.border}` : 'none',
      }}/>

      {/* Contenido */}
      <div style={{flex:1,padding:'11px 12px',display:'flex',
        flexDirection:'column',gap:6,minWidth:0}}>

        {/* Header: tipo + check */}
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
          <div style={{display:'flex',alignItems:'center',gap:5,color:p.text,opacity:0.75}}>
            <TypeIcon size={10} style={urgent ? {animation:'euIconWiggle 1.8s ease-in-out infinite'} : undefined}/>
            <span style={{fontFamily:'DM Sans,sans-serif',fontSize:8,
              letterSpacing:'0.12em',textTransform:'uppercase'}}>{DEADLINE_TYPE_LABEL[dl.type] || dl.type}</span>
          </div>
          {dl.type === 'partido' ? (
            <a href={`/bienestar/futbol?resultado=${dl.id}`}
              title="Ir a Fútbol — registrar resultado"
              style={{
                flexShrink:0,width:20,height:20,borderRadius:'50%',
                border:`1.5px solid ${p.border}`,
                background:'transparent',cursor:'pointer',
                display:'flex',alignItems:'center',justifyContent:'center',
                transition:'background 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = p.pill}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <IconHoverFx Icon={IconArrowRight} fx="pop" size={10} color={p.border}/>
            </a>
          ) : (
            <button
              onClick={() => onCheck(dl)}
              title="Marcar como cumplido"
              style={{
                flexShrink:0,width:20,height:20,borderRadius:'50%',
                border:`1.5px solid ${p.border}`,
                background:'transparent',cursor:'pointer',
                display:'flex',alignItems:'center',justifyContent:'center',
                transition:'background 0.15s',
                opacity: isChecking ? 0.4 : 1,
              }}
              onMouseEnter={e => e.currentTarget.style.background = p.pill}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <IconHoverFx Icon={IconCheck} fx="pop" size={10} color={p.border}/>
            </button>
          )}
        </div>

        {/* Nombre */}
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,fontWeight:500,
          color:C.text,lineHeight:1.3,
          overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}
          title={dl.label}>
          {dl.label}
        </div>

        {/* Badge + pulso */}
        <div style={{display:'flex',alignItems:'flex-end',
          justifyContent:'space-between',marginTop:'auto'}}>
          <div style={{background:p.pill,borderRadius:8,
            padding:'4px 9px',display:'inline-flex',
            alignItems:'baseline',gap:4}}>
            <span style={{
              fontFamily:'DM Sans,sans-serif',fontWeight:900,lineHeight:1,
              fontSize:['HOY','VENCIDO'].includes(dl.badge) ? 12 : 17,
              color:p.text,
            }}>{dl.badge}</span>
            <span style={{fontFamily:'DM Sans,sans-serif',fontSize:7,
              letterSpacing:'0.14em',color:p.text,opacity:0.6}}>{sublabel}</span>
          </div>
          {urgent && (
            <div style={{width:7,height:7,borderRadius:'50%',flexShrink:0,
              marginBottom:2,background:p.border,
              boxShadow:`0 0 6px ${p.border}`,
              animation:'blink 1.4s ease-in-out infinite'}}/>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Topbar notification bell — badge + dropdown, shares state with the ───
// sidebar Deadline Radar so checking an item off stays in sync everywhere.
function NotificationBell({ deadlines, checking, onCheck }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const hasUrgent = deadlines.some(d => d.level === 'red');

  useEffect(() => {
    if (!open) return;
    function onDocClick(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    function onKey(e) { if (e.key === 'Escape') setOpen(false); }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={ref} style={{position:'relative'}}>
      <button onClick={() => setOpen(o => !o)} title="Notificaciones" style={{
        position:'relative',background:'var(--gold-bg)',
        border:'1px solid color-mix(in srgb, var(--gold) 20%, transparent)',
        borderRadius:6,width:26,height:26,cursor:'pointer',
        display:'flex',alignItems:'center',justifyContent:'center',
      }}>
        <IconHoverFx Icon={IconBell} fx="wiggle" size={13} color="var(--gold)"/>
        {deadlines.length > 0 && (
          <span style={{
            position:'absolute',top:-4,right:-4,minWidth:14,height:14,borderRadius:7,
            background: hasUrgent ? '#ef4444' : 'var(--gold)',
            color: hasUrgent ? '#fff' : '#09070F',
            fontFamily:'DM Sans,sans-serif',fontSize:8,fontWeight:700,lineHeight:1,
            display:'flex',alignItems:'center',justifyContent:'center',padding:'0 3px',
            boxShadow: hasUrgent ? '0 0 6px #ef4444' : '0 0 6px var(--gold-glow)',
            animation: hasUrgent ? 'blink 1.4s ease-in-out infinite' : 'none',
          }}>{deadlines.length}</span>
        )}
      </button>

      {open && (
        <div style={{
          position:'absolute',top:'calc(100% + 10px)',right:0,zIndex:60,
          width:320,maxHeight:420,overflowY:'auto',
          background:'var(--surf)',border:'1px solid var(--gold-border)',
          borderRadius:14,padding:14,
          boxShadow:'0 20px 50px rgba(0,0,0,0.5)',
          animation:'euIconPop 0.18s ease',
        }}>
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:10}}>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
              color:C.textMuted,textTransform:'uppercase'}}>Notificaciones</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted,opacity:0.45}}>
              {deadlines.length} próximos
            </div>
          </div>
          {deadlines.length === 0 ? (
            <div style={{padding:'20px 4px',textAlign:'center',
              fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textMuted}}>
              Sin pendientes por ahora ✦
            </div>
          ) : (
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {deadlines.map((dl, i) => (
                <DeadlineItemCard key={`${dl.type}-${dl.id ?? i}`} dl={dl}
                  isChecking={checking[dl.id]} onCheck={onCheck}/>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Small hover-triggered icon button (wiggle/pop/spin on hover) ─────────
function IconHoverFx({ Icon, size = 14, fx = 'wiggle', color, style, iconStyle }) {
  const [hov, setHov] = useState(false);
  const FX = {
    wiggle: 'euIconWiggle 0.5s ease',
    pop:    'euIconPop 0.4s ease',
    spin:   'euIconSpinSlow 0.6s linear',
  };
  return (
    <span
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{ display:'inline-flex', color, ...style }}>
      <Icon size={size} style={{ animation: hov ? FX[fx] : 'none', ...iconStyle }}/>
    </span>
  );
}

function todayQuote() {
  const dayIndex = Math.floor(Date.now() / 86400000);
  return EU.quotes[dayIndex % EU.quotes.length];
}

// ═══════════════════════════════════════════════════════════
// REFLEXION DEL DÍA
// ═══════════════════════════════════════════════════════════
function ReflexionDelDia() {
  const initial = (window.EU._server || {}).reflexion || null;
  const [quote, setQuote] = useState(initial || todayQuote());
  const [spinning, setSpinning] = useState(false);

  const CATEGORY_LABEL = { stoic: 'Estoica', motivational: 'Motivacional' };
  const CATEGORY_COLOR = {
    stoic:       { text: '#a78bfa', bg: 'rgba(167,139,250,0.08)', border: 'rgba(167,139,250,0.18)' },
    motivational:{ text: '#34d399', bg: 'rgba(52,211,153,0.08)',  border: 'rgba(52,211,153,0.18)'  },
  };
  const cat = CATEGORY_COLOR[quote.category] || CATEGORY_COLOR.stoic;

  async function refresh() {
    setSpinning(true);
    try {
      const r = await fetch('/api/quote/refresh');
      setQuote(await r.json());
    } catch(e) {}
    setSpinning(false);
  }

  return (
    <div style={{marginBottom:14}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase'}}>Reflexión del Día</div>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          {quote.category && (
            <span style={{fontFamily:'DM Sans,sans-serif',fontSize:8,
              color:cat.text,background:cat.bg,border:`1px solid ${cat.border}`,
              padding:'2px 8px',borderRadius:100,letterSpacing:'0.06em'}}>
              {CATEGORY_LABEL[quote.category] || quote.category}
            </span>
          )}
          <button onClick={refresh} style={{
            background:'transparent',border:'none',cursor:'pointer',
            color:C.textMuted,padding:0,lineHeight:1,
            display:'inline-flex',alignItems:'center',
            transform:spinning?'rotate(180deg)':'rotate(0deg)',
            transition:'transform 0.4s ease',
          }}>
            <IconHoverFx Icon={IconRefreshCw} fx="spin" size={14}/>
          </button>
        </div>
      </div>
      <QuoteDisplay quote={quote}/>
    </div>
  );
}
function fmtDate() {
  const d = new Date();
  const days = ['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];
  const mos  = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  return `${days[d.getDay()]} ${d.getDate()} de ${mos[d.getMonth()]}`;
}

// ═══════════════════════════════════════════════════════════
// WORD OF THE DAY
// ═══════════════════════════════════════════════════════════
function WordOfDay() {
  const [word, setWord] = useState((window.EU._server || {}).word || null);
  const [spinning, setSpinning] = useState(false);

  if (!word) return null;

  async function refresh() {
    setSpinning(true);
    try {
      const r = await fetch('/api/word/refresh');
      setWord(await r.json());
    } catch(e) {}
    setSpinning(false);
  }

  return (
    <div style={{
      background:'color-mix(in srgb, var(--gold) 4%, transparent)',
      border:'1px solid var(--gold-bg)',
      borderRadius:12, padding:'16px 18px', marginBottom:14,
    }}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase'}}>Word of the Day</div>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span style={{fontFamily:'DM Sans,sans-serif',fontSize:8,color:'#60a5fa',
            background:'rgba(96,165,250,0.08)',border:'1px solid rgba(96,165,250,0.18)',
            padding:'2px 8px',borderRadius:100,letterSpacing:'0.06em',whiteSpace:'nowrap'}}>EN → FR</span>
          <button onClick={refresh} style={{
            background:'transparent',border:'none',cursor:'pointer',
            color:C.textMuted,padding:0,lineHeight:1,
            display:'inline-flex',alignItems:'center',
            transform:spinning?'rotate(180deg)':'rotate(0deg)',
            transition:'transform 0.4s ease',
          }}>
            <IconHoverFx Icon={IconRefreshCw} fx="spin" size={14}/>
          </button>
        </div>
      </div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted,marginBottom:2,letterSpacing:'0.04em'}}>
        {word.phonetic}
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
        fontSize:26,fontWeight:300,color:C.text,lineHeight:1,marginBottom:10}}>
        {word.word}
      </div>
      <div style={{height:1,background:'linear-gradient(90deg,var(--gold-glow),transparent)',marginBottom:10}}/>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textMuted,lineHeight:1.55,marginBottom:8}}>
        {word.meaning}
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',fontSize:12,
        color:C.textMuted,borderLeft:'2px solid var(--b2)',
        paddingLeft:10,marginBottom:10,lineHeight:1.55,opacity:0.75}}>
        "{word.example}"
      </div>
      <span style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
        background:'color-mix(in srgb, var(--gold) 6%, transparent)',border:'1px solid var(--gold-border)',
        color:C.gold,padding:'3px 9px',borderRadius:100,display:'inline-block'}}>
        🇫🇷 {word.french}
      </span>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// REMINDERS WIDGET
// ═══════════════════════════════════════════════════════════
function RemindersWidget() {
  const initial = (window.EU._server || {}).reminders || [];
  const [items, setItems] = useState(initial);

  if (!items.length) return null;

  const FREQ_LABELS = { dias: 'días', semanas: 'semanas', meses: 'meses' };

  async function handleDone(id, type) {
    setItems(prev => prev.map(r => r.id === id ? {...r, _loading: true} : r));
    try {
      const res = await fetch(`/perfil/api/reminder/${id}/done`, { method: 'POST' });
      const j = await res.json();
      if (j.ok) {
        if (type === 'unico') {
          setItems(prev => prev.filter(r => r.id !== id));
        } else {
          const res2 = await fetch('/perfil/api/reminders');
          const all = await res2.json();
          const today7 = new Date(); today7.setDate(today7.getDate() + 7);
          const iso7 = today7.toISOString().slice(0, 10);
          setItems(all.filter(r => {
            const d = r.next_date || r.target_date || '9999-12-31';
            return d <= iso7;
          }).slice(0, 5));
        }
      }
    } catch(e) {
      setItems(prev => prev.map(r => r.id === id ? {...r, _loading: false} : r));
    }
  }

  return (
    <div style={{marginBottom:14}}>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Recordatorios</div>
      <div style={{
        background:'color-mix(in srgb, var(--gold) 3%, transparent)',
        border:'1px solid var(--gold-bg)',
        borderRadius:12, overflow:'hidden',
      }}>
        {items.map((r, i) => {
          const dateStr = r.next_date || r.target_date || '';
          const isPeriodic = r.type === 'periodico';
          return (
            <div key={r.id} style={{
              display:'flex', alignItems:'center', gap:12,
              padding:'12px 16px',
              borderBottom: i < items.length - 1 ? '1px solid color-mix(in srgb, var(--gold) 6%, transparent)' : 'none',
              opacity: r._loading ? 0.4 : 1, transition:'opacity 0.2s',
            }}>
              <button onClick={() => !r._loading && handleDone(r.id, r.type)} style={{
                flexShrink:0, background:'none', border:'1.5px solid color-mix(in srgb, var(--gold) 25%, transparent)',
                width:18, height:18, borderRadius:'50%', cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center',
                transition:'border-color 0.15s, background 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor='var(--gold)'; e.currentTarget.style.background='var(--gold-bg)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor='color-mix(in srgb, var(--gold) 25%, transparent)'; e.currentTarget.style.background='none'; }}
              />
              <div style={{flex:1, minWidth:0}}>
                <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text,
                  overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                  {r.description}
                </div>
                <div style={{display:'flex',gap:6,alignItems:'center',marginTop:3}}>
                  {isPeriodic ? (
                    <span style={{fontFamily:'DM Sans,sans-serif',fontSize:8,
                      background:'rgba(167,139,250,0.1)',border:'1px solid rgba(167,139,250,0.2)',
                      color:'#a78bfa',padding:'1px 7px',borderRadius:100,letterSpacing:'0.06em'}}>
                      cada {r.freq_value} {FREQ_LABELS[r.freq_unit] || r.freq_unit}
                    </span>
                  ) : (
                    <span style={{fontFamily:'DM Sans,sans-serif',fontSize:8,
                      background:'rgba(96,165,250,0.08)',border:'1px solid rgba(96,165,250,0.15)',
                      color:'#60a5fa',padding:'1px 7px',borderRadius:100,letterSpacing:'0.06em'}}>
                      único
                    </span>
                  )}
                  {dateStr && (
                    <span style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>
                      {dateStr}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// DEADLINE RADAR
// ═══════════════════════════════════════════════════════════
function DeadlineRadar({ deadlines, checking, onCheck }) {
  if (!deadlines.length) return null;

  return (
    <div style={{marginBottom:14}}>
      {/* Header */}
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10}}>
        <div style={{
          width:6,height:6,borderRadius:'50%',
          background:'#ef4444',boxShadow:'0 0 7px #ef4444',
          animation:'blink 1.4s ease-in-out infinite',
          flexShrink:0,
        }}/>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',flex:1}}>Deadline Radar</div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
          color:C.textMuted,opacity:0.45}}>{deadlines.length} próximos</div>
      </div>

      {/* Lista — una sola columna, sin scroll oculto */}
      <div style={{display:'flex',flexDirection:'column',gap:8}}>
        {deadlines.map((dl, i) => (
          <DeadlineItemCard key={`${dl.type}-${dl.id ?? i}`} dl={dl}
            isChecking={checking[dl.id]} onCheck={onCheck}/>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// DAILY SCORE CARD
// ═══════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════
// HOME SCREEN
// ═══════════════════════════════════════════════════════════
const TIERS = [
  { rank:'carbon',  Icon:IconMountain, label:'Carbón',   color:'#94a3b8', threshold:0  },
  { rank:'iron',    Icon:IconSwords,   label:'Hierro',   color:'#eab308', threshold:8  },
  { rank:'gold',    Icon:IconMedal,    label:'Oro',      color:'#fbbf24', threshold:16 },
  { rank:'diamond', Icon:IconGem,      label:'Diamante', color:'#7dd3fc', threshold:20 },
];

function titleCase(s) {
  return s.charAt(0) + s.slice(1).toLowerCase();
}

function SuggestionCard({ suggestion, onClick, tint }) {
  const [hov, setHov] = useState(false);
  return (
    <div onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background:tint.bg, border:`1px solid ${tint.border}`,
        borderRadius:12,padding:'14px 16px',marginBottom:14,cursor:'pointer',
        display:'flex',alignItems:'center',gap:12,
        transform: hov ? 'translateY(-2px)' : 'translateY(0)',
        boxShadow: hov ? '0 10px 24px rgba(0,0,0,0.3)' : 'none',
        transition:'transform 0.18s, box-shadow 0.18s',
      }}>
      <div style={{width:34,height:34,borderRadius:9,background:'rgba(0,0,0,0.15)',
        display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
        <IconZap size={16} style={{color:tint.text,animation:'euIconWiggle 2.4s ease-in-out infinite'}}/>
      </div>
      <div style={{flex:1}}>
        <div style={{fontSize:9,letterSpacing:'0.16em',textTransform:'uppercase',
          color:tint.text,marginBottom:4}}>
          Un click cierra {suggestion.cat}
        </div>
        <div style={{fontSize:14,color:C.text}}>{suggestion.label}</div>
      </div>
      <span style={{fontSize:13,color:C.gold,fontWeight:600,flexShrink:0}}>+{suggestion.pts} XP</span>
    </div>
  );
}

function ModuleStripCard({ mod, onClick }) {
  const [hov, setHov] = useState(false);
  const acc = EU.catTint(mod.hue, 'text');
  const Icon = MODULE_ICONS[mod.id] || IconTerminal;
  return (
    <div onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background:C.card, border:`1px solid ${mod.done ? acc : C.goldBorder}`,
        borderRadius:13,padding:14,cursor:'pointer',
        boxShadow: mod.done ? `0 0 16px color-mix(in srgb, ${acc} 30%, transparent)` : 'none',
        transform: hov ? 'translateY(-3px)' : 'translateY(0)',
        transition:'transform 0.18s, box-shadow 0.18s, border-color 0.18s',
      }}>
      <div style={{
        width:36,height:36,borderRadius:10,marginBottom:10,
        display:'flex',alignItems:'center',justifyContent:'center',
        background:`color-mix(in srgb, ${acc} 14%, transparent)`,
        border:`1px solid color-mix(in srgb, ${acc} 35%, transparent)`,
      }}>
        <Icon size={17} style={{
          color:acc,
          animation: mod.done
            ? 'euIconFloat 2.6s ease-in-out infinite'
            : (hov ? 'euIconPulseScale 0.5s ease' : 'none'),
        }}/>
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:15,fontWeight:600,
        color:C.text,letterSpacing:'0.02em'}}>{titleCase(mod.name)}</div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9.5,color:C.textMuted,
        marginTop:2,lineHeight:1.35}}>{mod.desc}</div>
      <div style={{display:'flex',alignItems:'center',gap:5,marginTop:10,fontSize:9.5}}>
        <span style={{width:6,height:6,borderRadius:'50%',background:mod.done?acc:C.textMuted,flexShrink:0}}/>
        <span style={{color:mod.done?acc:C.textMuted}}>{mod.done ? `${mod.streak} días` : 'pendiente hoy'}</span>
      </div>
    </div>
  );
}

function HomeScreen({ appState, dispatch, isDesktop }) {
  const { isLight } = useTheme();
  const { level, xp, xpNext, modules } = appState;
  const lv = EU.levels[level - 1];
  const xpPct = xpNext ? xp / xpNext : 1;
  const srv = window.EU._server || {};
  const xpToday = srv.xpToday || 0;
  const streak  = srv.streak  || 0;
  const clf     = srv.classification || {};
  const XP_GOAL = 15;
  const xpDayPct = Math.min(1, xpToday / XP_GOAL);

  const [suggestion, setSuggestion] = React.useState(srv.suggestion || null);
  const { deadlines, checking, handleCheck } = useDeadlines();

  const logActivityFromHome = (key) => {
    if (suggestion?.key === key) setSuggestion(null);
    const updated = (window.EU._server.activities || []).map(a =>
      a.key === key ? {...a, done: !a.done} : a
    );
    window.EU._server.activities = updated;
    fetch('/actividades/api/activity/log', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({key}),
    })
    .then(r => r.json())
    .then(data => {
      if (data.gam && (data.gam.xp_delta || data.gam.xp))
        dispatch({type:'ADD_XP', amount: data.gam.xp_delta || data.gam.xp});
      if (data.gam?.achievements?.length) window.euFireAchievements(data.gam.achievements);
      if (data.gam?.perfect_day) {
        window.dispatchEvent(new CustomEvent('eu:perfect-day', {
          detail: { bonusXp: data.gam.perfect_day.xp || 5, bonusEc: data.gam.perfect_day.ec || 10 }
        }));
      } else if (data.gam?.combo_bonuses?.length) {
        data.gam.combo_bonuses.forEach(c =>
          window.dispatchEvent(new CustomEvent('eu:combo-bonus', { detail: c }))
        );
      }
      if (data.stats) {
        window.EU._server.xpToday = data.stats.xp_today ?? data.stats.pts_today ?? xpToday;
        window.EU._server.streak  = data.stats.streak ?? streak;
      }
    })
    .catch(() => {});
  };

  // ── Shared blocks ──────────────────────────────────────────
  const heroXp = (
    <div style={{
      background:'linear-gradient(140deg, var(--surf), var(--bg))',
      border:'1px solid var(--gold-border)',
      borderRadius:16,padding:'20px',marginBottom:14,
      position:'relative',overflow:'hidden',
    }}>
      <div style={{fontSize:9,letterSpacing:'0.18em',color:C.gold,
        opacity:0.6,textTransform:'uppercase',marginBottom:6}}>XP hoy</div>
      <div style={{display:'flex',alignItems:'baseline',gap:8,marginBottom:12}}>
        <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:48,
          lineHeight:1,color:C.goldLight,fontWeight:600}}>{xpToday}</div>
        <div style={{fontSize:13,color:C.textMuted}}>/ {XP_GOAL} meta</div>
      </div>
      <div style={{height:5,background:'var(--gold-bg)',borderRadius:3,overflow:'hidden',marginBottom:12}}>
        <div style={{
          height:'100%',borderRadius:3,
          background:'linear-gradient(90deg, color-mix(in srgb, var(--gold) 60%, transparent), var(--gold), var(--gold-l))',
          width:`${xpDayPct*100}%`,
          boxShadow:'0 0 8px var(--gold-glow)',
          transition:'width 0.8s ease',
        }}/>
      </div>
      {(() => {
        const ci = Math.max(0, TIERS.findIndex(t => t.rank === clf.rank));
        const nt = TIERS[ci + 1] || null;
        return (
          <>
            <div style={{display:'flex',alignItems:'stretch',gap:6,marginBottom:10}}>
              {TIERS.map((t, i) => {
                const active = i === ci;
                const TIcon = t.Icon;
                return (
                  <div key={t.rank} style={{
                    flex:1,display:'flex',flexDirection:'column',alignItems:'center',gap:6,
                    padding:'10px 4px',borderRadius:10,
                    border:`1px solid ${active ? t.color : 'transparent'}`,
                    background: active ? `color-mix(in srgb, ${t.color} 8%, transparent)` : 'transparent',
                    boxShadow: active ? `0 0 16px color-mix(in srgb, ${t.color} 25%, transparent)` : 'none',
                    transition:'all 0.25s',
                  }}>
                    <div style={{
                      width:26,height:26,borderRadius:'50%',
                      display:'flex',alignItems:'center',justifyContent:'center',
                      background: active ? t.color : 'rgba(255,255,255,0.04)',
                      boxShadow: active ? `0 0 10px ${t.color}` : 'none',
                      transition:'all 0.25s',
                    }}>
                      <TIcon size={13} style={{
                        color: active ? '#09070F' : C.textMuted,
                        animation: active
                          ? 'euIconPop 0.5s ease 0.1s both, euIconPulseScale 2.2s ease-in-out 1s infinite'
                          : 'none',
                      }}/>
                    </div>
                    <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.06em',
                      color: active ? t.color : C.textMuted, fontWeight: active ? 600 : 400,
                      opacity: active ? 1 : 0.6, textAlign:'center'}}>{t.label}</div>
                  </div>
                );
              })}
            </div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',fontSize:10}}>
              <span style={{color:C.textMuted}}>Clasificación de hoy</span>
              <span style={{color:C.gold,opacity:0.8}}>
                {nt?`${nt.threshold-xpToday} XP → ${nt.label}`:'✦ Diamante alcanzado'}
              </span>
            </div>
          </>
        );
      })()}
    </div>
  );

  const levelCard = (
    <div style={{
      background:'linear-gradient(140deg, var(--card), var(--surf) 55%, var(--bg))',
      border:'1px solid color-mix(in srgb, var(--gold) 20%, transparent)',
      borderRadius:16,padding:'18px 16px',marginBottom:14,
      position:'relative',overflow:'hidden',
    }}>
      <div style={{position:'absolute',inset:0,pointerEvents:'none',background:
        'radial-gradient(ellipse at 15% 85%,color-mix(in srgb, var(--gold) 5%, transparent) 0%,transparent 55%),' +
        'radial-gradient(ellipse at 85% 15%,color-mix(in srgb, var(--gold) 3%, transparent) 0%,transparent 45%)'}}/>
      <div style={{display:'flex',alignItems:'flex-end',gap:14}}>
        <div style={{flexShrink:0,cursor:'pointer',transition:'opacity 0.15s'}}
          onClick={()=>window.location.reload()}
          onMouseDown={e=>e.currentTarget.style.opacity='0.5'}
          onMouseUp={e=>e.currentTarget.style.opacity='1'}>
          <GreekColumn level={level} xpPct={xpPct} size={72}/>
        </div>
        <div style={{flex:1,paddingBottom:3}}>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
            letterSpacing:'0.18em',color:C.gold,opacity:0.6,textTransform:'uppercase',marginBottom:2}}>
            NIVEL {level}
          </div>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:28,
            fontWeight:600,color:C.text,lineHeight:1,letterSpacing:'0.05em'}}>{lv?.name}</div>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
            fontSize:12,color:C.textSub,marginTop:3,marginBottom:10}}>{lv?.sub}</div>
          <div style={{height:3,background:'var(--gold-bg)',borderRadius:2,overflow:'hidden'}}>
            <div style={{height:'100%',borderRadius:2,
              background:'linear-gradient(90deg, color-mix(in srgb, var(--gold) 60%, transparent), var(--gold), var(--gold-l))',
              width:`${xpPct*100}%`,boxShadow:'0 0 8px var(--gold-glow)',transition:'width 1.2s ease'}}/>
          </div>
        </div>
      </div>
    </div>
  );

  const modulesStrip = (
    <div style={{marginBottom:14}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:8}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase'}}>Módulos</div>
        <div style={{fontSize:11,color:C.textMuted}}>
          {modules.filter(m=>m.done).length} de {modules.length}
        </div>
      </div>
      <div style={{display:'flex',gap:3,marginBottom:14,height:3,borderRadius:2,overflow:'hidden',
        background:'color-mix(in srgb, var(--gold) 6%, transparent)'}}>
        {modules.map(mod=>(
          <div key={mod.id} style={{flex:1,height:'100%',
            background:mod.done?EU.catTint(mod.hue,'text'):'transparent',transition:'background 0.4s'}}/>
        ))}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(150px,1fr))',gap:10}}>
        {modules.map(mod=>(
          <ModuleStripCard key={mod.id} mod={mod}
            onClick={()=>mod.route?(window.location.href=mod.route):dispatch({type:'OPEN_MODULE',id:mod.id})}/>
        ))}
      </div>
    </div>
  );

  const heatmapCard = (
    <div style={{background:C.card,border:`1px solid ${C.goldBorder}`,
      borderRadius:12,padding:'14px 16px',marginBottom:14}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:10}}>
        <div style={{fontSize:10,letterSpacing:'0.18em',color:C.gold,
          opacity:0.7,textTransform:'uppercase'}}>Racha · {streak} días</div>
        <a href="/logros" style={{fontSize:10,color:C.gold,opacity:0.6,textDecoration:'none'}}>
          Ver historial →
        </a>
      </div>
      <StreakHeatmap days={21} compact={true}/>
    </div>
  );

  const suggestionCard = suggestion && (
    <SuggestionCard suggestion={suggestion} onClick={()=>logActivityFromHome(suggestion.key)}
      tint={{
        bg:     EU.catTint((EU.catHues||{})[suggestion.cat]||45,'bg'),
        border: EU.catTint((EU.catHues||{})[suggestion.cat]||45,'border'),
        text:   EU.catTint((EU.catHues||{})[suggestion.cat]||45,'text'),
      }}/>
  );

  // ── Desktop 2-column layout ─────────────────────────────────
  if (isDesktop) {
    return (
      <div style={{minHeight:'100vh'}}>
        {/* Desktop sticky topbar */}
        <div style={{
          position:'sticky',top:0,zIndex:50,
          padding:'14px 40px',
          background:'var(--surf-top)',
          borderBottom:'1px solid color-mix(in srgb, var(--gold) 7%, transparent)',
          display:'flex',justifyContent:'space-between',alignItems:'center',
        }}>
          <div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              letterSpacing:'0.22em',color:C.gold,opacity:0.65,textTransform:'uppercase'}}>
              {fmtDate()}
            </div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:22,
              color:C.text,fontWeight:500,letterSpacing:'0.14em',marginTop:1}}>
              Ε Υ Δ Α Ι Μ Ο Ν Ι Α
            </div>
          </div>
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <button onClick={()=>window.dispatchEvent(new CustomEvent('eu:open-cmdk'))}
              style={{background:'var(--gold-bg)',border:'1px solid color-mix(in srgb, var(--gold) 20%, transparent)',
                borderRadius:6,padding:'5px 10px',color:C.gold,fontSize:11,cursor:'pointer',
                fontFamily:'DM Sans,sans-serif',letterSpacing:'0.05em',
                display:'inline-flex',alignItems:'center',gap:5}}>
              <IconHoverFx Icon={IconCommand} fx="wiggle" size={11}/> K
            </button>
            <NotificationBell deadlines={deadlines} checking={checking} onCheck={handleCheck}/>
            <a href="/logros" style={{display:'inline-flex',alignItems:'center',gap:5,
              fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.gold,opacity:0.65,
              textDecoration:'none',letterSpacing:'0.08em'}}>
              <IconHoverFx Icon={IconTrophy} fx="pop" size={11}/> Logros
            </a>
          </div>
        </div>

        {/* 2-column grid */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 380px',gap:'0 32px',
          padding:'32px 40px 60px',alignItems:'start'}}>

          {/* LEFT — main content */}
          <div>
            <div style={{marginBottom:20,animation:'euRise 0.5s ease 0.02s both'}}>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:26,color:C.text}}>
                Buenos días, Gio.
              </div>
              <div style={{fontSize:11,color:C.textMuted,marginTop:3}}>
                {fmtDate()} · día {streak} de tu racha
              </div>
            </div>
            <div style={{animation:'euRise 0.5s ease 0.06s both'}}>{heroXp}</div>
            {suggestionCard && <div style={{animation:'euRise 0.5s ease 0.10s both'}}>{suggestionCard}</div>}
            <div style={{animation:'euRise 0.5s ease 0.14s both'}}>{levelCard}</div>
            <div style={{animation:'euRise 0.5s ease 0.18s both'}}>{modulesStrip}</div>
            <div style={{animation:'euRise 0.5s ease 0.24s both'}}><ReflexionDelDia/></div>
          </div>

          {/* RIGHT — sidebar widgets */}
          <div style={{position:'sticky',top:80}}>
            <div style={{animation:'euRise 0.5s ease 0.08s both'}}>{heatmapCard}</div>
            <div style={{animation:'euRise 0.5s ease 0.14s both'}}><WordOfDay/></div>
            <div style={{animation:'euRise 0.5s ease 0.20s both'}}><DeadlineRadar deadlines={deadlines} checking={checking} onCheck={handleCheck}/></div>
          </div>
        </div>
      </div>
    );
  }

  // ── Mobile layout ───────────────────────────────────────────
  return (
    <div style={{paddingBottom:100, minHeight:'100vh'}}>
      {/* Mobile sticky header */}
      <div style={{
        position:'sticky',top:0,zIndex:50,
        padding:'env(safe-area-inset-top,16px) 20px 12px',
        paddingTop:'max(env(safe-area-inset-top,16px),16px)',
        background:EU.rgba('deep', 0.97),
        borderBottom:'1px solid color-mix(in srgb, var(--gold) 7%, transparent)',
      }}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
          <div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              letterSpacing:'0.22em',color:C.gold,opacity:0.65,textTransform:'uppercase'}}>
              {fmtDate()}
            </div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:20,
              color:C.text,fontWeight:500,letterSpacing:'0.18em',marginTop:1}}>
              ΕΥΔΑΙΜΟΝΙΑ
            </div>
          </div>
          <div style={{display:'flex',alignItems:'center',gap:10,paddingTop:2}}>
            <NotificationBell deadlines={deadlines} checking={checking} onCheck={handleCheck}/>
            <a href="/logros" style={{display:'inline-flex',alignItems:'center',gap:5,
              fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.gold,opacity:0.65,
              textDecoration:'none',letterSpacing:'0.08em'}}>
              <IconHoverFx Icon={IconTrophy} fx="pop" size={11}/> Logros
            </a>
          </div>
        </div>
      </div>

      <div style={{padding:'0 16px'}}>
        <div style={{padding:'20px 0 12px',animation:'euRise 0.5s ease 0.02s both'}}>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:22,color:C.text}}>
            Buenos días, Gio.
          </div>
          <div style={{fontSize:11,color:C.textMuted,marginTop:2}}>
            {fmtDate()} · día {streak} de tu racha
          </div>
        </div>
        <div style={{animation:'euRise 0.5s ease 0.06s both'}}>{heroXp}</div>
        {suggestionCard && <div style={{animation:'euRise 0.5s ease 0.10s both'}}>{suggestionCard}</div>}
        <div style={{animation:'euRise 0.5s ease 0.14s both'}}>{levelCard}</div>
        <div style={{animation:'euRise 0.5s ease 0.18s both'}}>{modulesStrip}</div>
        <div style={{animation:'euRise 0.5s ease 0.22s both'}}>{heatmapCard}</div>
        <div style={{animation:'euRise 0.5s ease 0.26s both'}}><ReflexionDelDia/></div>
        <div style={{animation:'euRise 0.5s ease 0.30s both'}}><WordOfDay/></div>
        <div style={{animation:'euRise 0.5s ease 0.34s both'}}><DeadlineRadar deadlines={deadlines} checking={checking} onCheck={handleCheck}/></div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// COMMAND CENTER
// ═══════════════════════════════════════════════════════════
function CommandCenterScreen({ appState, dispatch, isDesktop }) {
  const { modules } = appState;
  const doneCount = modules.filter(m => m.done).length;
  const cols = isDesktop ? '1fr 1fr 1fr' : '1fr 1fr';

  return (
    <div style={{paddingBottom: isDesktop ? 48 : 100, minHeight:'100vh'}}>
      <div style={{padding: isDesktop ? '28px 24px 20px' : '16px 20px 20px'}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.2em',
          color:C.gold,textTransform:'uppercase',opacity:0.6,marginBottom:4}}>
          COMMAND CENTER
        </div>
        <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:30,
          fontWeight:600,color:C.text,letterSpacing:'0.05em'}}>Módulos</div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:11,color:C.textMuted,marginTop:4}}>
          {doneCount} de {modules.length} completados hoy
        </div>
        {/* Daily XP mini strip */}
        <div style={{
          display:'flex',gap:4,marginTop:14,
          height:3,borderRadius:2,overflow:'hidden',background:'color-mix(in srgb, var(--gold) 6%, transparent)',
        }}>
          {modules.map(mod => (
            <div key={mod.id} style={{
              flex:1,height:'100%',
              background: mod.done ? EU.catTint(mod.hue, 'text') : 'transparent',
              transition:'background 0.4s',
            }}/>
          ))}
        </div>
      </div>

      <div style={{padding: isDesktop ? '0 24px' : '0 16px', display:'grid', gridTemplateColumns:cols, gap:10}}>
        {modules.map(mod => (
          <ModuleStripCard key={mod.id} mod={mod}
            onClick={() => mod.route ? (window.location.href = mod.route) : dispatch({type:'OPEN_MODULE',id:mod.id})}/>
        ))}
        {/* PRAXIS + LOGROS — bottom full-width cards */}
        <a href="/gtd"
          style={{
            gridColumn:'1/-1',
            background:C.card,border:'1px solid var(--b)',
            borderRadius:14,padding:'14px 15px',cursor:'pointer',
            display:'flex',justifyContent:'space-between',alignItems:'center',
            transition:'all 0.25s', textDecoration:'none',
          }}>
          <div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:15,
              fontWeight:600,color:C.text,letterSpacing:'0.08em'}}>PRAXIS</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              color:C.gold,letterSpacing:'0.1em',textTransform:'uppercase',marginTop:3}}>
              Ejecución de la voluntad · GTD
            </div>
          </div>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:22,color:C.gold,opacity:0.5}}>→</div>
        </a>
        <a href="/logros"
          style={{
            gridColumn:'1/-1',
            background:'color-mix(in srgb, var(--gold) 4%, transparent)',
            border:'1px solid var(--b)',
            borderRadius:14,padding:'14px 15px',cursor:'pointer',
            display:'flex',justifyContent:'space-between',alignItems:'center',
            transition:'all 0.25s', textDecoration:'none',
          }}>
          <div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:15,
              fontWeight:600,color:C.text,letterSpacing:'0.08em'}}>🏆 LOGROS</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              color:C.gold,letterSpacing:'0.1em',textTransform:'uppercase',marginTop:3}}>
              Trofeos · Clasificación · Historial XP
            </div>
          </div>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:22,color:C.gold,opacity:0.5}}>→</div>
        </a>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// MODULE DETAIL
// ═══════════════════════════════════════════════════════════
function ModuleDetailScreen({ mod, appState, dispatch, isDesktop }) {
  const acc    = EU.catTint(mod.hue, 'text');
  const accMid = EU.catTint(mod.hue, 'border');

  return (
    <div style={{minHeight:'100vh', paddingBottom: isDesktop ? 48 : 100}}>
      {/* Hero header */}
      <div style={{
        padding: isDesktop ? '28px 24px 28px' : '16px 20px 24px',
        background:`linear-gradient(170deg,${EU.catTint(mod.hue, 'bg')} 0%,transparent 100%)`,
        borderBottom:`1px solid ${accMid}`,
      }}>
        <div style={{display:'flex',alignItems:'center',marginBottom:14}}>
          <button onClick={() => dispatch({type:'CLOSE_MODULE'})}
            style={{background:'none',border:'none',color:C.textMuted,
              fontFamily:'DM Sans,sans-serif',fontSize:12,cursor:'pointer',
              padding:0,display:'flex',alignItems:'center',gap:6}}>
            ← Módulos
          </button>
        </div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:acc,textTransform:'uppercase',opacity:0.85,marginBottom:3}}>
          {mod.concept}
        </div>
        <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:32,
          fontWeight:600,color:C.text,letterSpacing:'0.06em'}}>
          {mod.name}
        </div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:11,color:C.textMuted,marginTop:3}}>
          {mod.desc}
        </div>
      </div>

      <div style={{padding: isDesktop ? '24px 24px 0' : '20px 16px 0'}}>
        <ModuleExtra id={mod.id} acc={acc} isDesktop={isDesktop}/>
      </div>
    </div>
  );
}

function OikonomiaExtra() {
  const [data, setData]       = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    fetch('/finanzas/api/oikonomia-summary')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const fmt = v => (v != null && v !== '') ? `$${Number(v).toLocaleString('es-MX', {maximumFractionDigits:0})}` : '—';
  const GOLD    = '#E8C96D';
  const CARD_BG = 'linear-gradient(150deg,#1a1510 0%,#241d14 55%,#16110b 100%)';
  const CARD_BR = '1px solid rgba(201,168,76,0.28)';

  if (loading) return (
    <div style={{textAlign:'center',padding:'24px 0',fontFamily:'DM Sans,sans-serif',
      fontSize:11,color:C.textMuted,letterSpacing:'0.1em'}}>cargando…</div>
  );

  if (!data || data.locked) return (
    <div style={{background:C.card,border:'1px solid var(--b)',borderRadius:16,
      padding:'28px 20px',textAlign:'center'}}>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:26,color:GOLD,marginBottom:8}}>
        Oikonomia 🔒
      </div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:11,color:C.textMuted,marginBottom:18}}>
        Activa tu módulo financiero para ver tu patrimonio neto.
      </div>
      <a href="/finanzas/" style={{display:'inline-block',background:GOLD,color:'#1a1510',
        fontFamily:'DM Sans,sans-serif',fontSize:12,fontWeight:600,
        padding:'10px 24px',borderRadius:10,textDecoration:'none'}}>
        Desbloquear Oikonomia 🔒
      </a>
    </div>
  );

  const trendPos    = data.trend_pct >= 0;
  const trendSymbol = trendPos ? '▲' : '▼';
  const trendColor  = trendPos ? '#7BC49A' : '#E59B92';

  // Bar-chart sparkline (matches mockup design)
  const spark = (data.spark || []).filter(v => v != null && v !== '');
  let sparkBars = null;
  if (spark.length >= 2) {
    const min   = Math.min(...spark);
    const max   = Math.max(...spark);
    const range = max - min || 1;
    sparkBars = (
      <div style={{display:'flex',alignItems:'flex-end',gap:3,height:36,
        marginTop:14,marginBottom:2}}>
        {spark.map((v, i) => {
          const pct    = Math.max(8, ((v - min) / range) * 92 + 8);
          const isLast = i === spark.length - 1;
          return (
            <div key={i} style={{
              flex: 1, height:`${pct}%`,
              background: isLast
                ? 'linear-gradient(180deg,#E8C96D,rgba(201,168,76,0.3))'
                : 'linear-gradient(180deg,rgba(201,168,76,0.55),rgba(201,168,76,0.12))',
              borderRadius:'2px 2px 0 0',
              boxShadow: isLast ? '0 0 10px rgba(201,168,76,0.5)' : 'none',
            }}/>
          );
        })}
      </div>
    );
  }

  const pillars = [
    {icon:'🏛️', label:'Patrimonio',  sub:'Cuentas · deudas · bienes',
     href:'/finanzas/',       iconBg:'rgba(58,95,138,0.12)',
     statV: String(data.n_cuentas), statL:'cuentas'},
    {icon:'📊', label:'Presupuesto', sub:'50 · 30 · 20',
     href:'/finanzas/budget', iconBg:'rgba(26,122,82,0.12)',
     statV: null, statL: null},
    {icon:'📈', label:'Inversiones', sub:'Portafolio · rendimientos',
     href:'/finanzas/inversiones', iconBg:'rgba(34,197,94,0.10)',
     statV: null, statL: null},
    {icon:'💳', label:'Estados',     sub:'Movimientos · análisis',
     href:'/finanzas/estados',iconBg:'rgba(139,105,20,0.12)',
     statV: String(data.n_bancos), statL:'bancos'},
  ];

  return (
    <div>
      {/* Net-worth black card */}
      <div style={{position:'relative',overflow:'hidden',background:CARD_BG,
        borderRadius:18,padding:'22px 22px 20px',marginBottom:14,border:CARD_BR,
        boxShadow:'0 16px 40px -16px rgba(40,28,8,0.55)'}}>
        {/* radial highlight */}
        <div style={{position:'absolute',inset:0,pointerEvents:'none',
          background:'radial-gradient(ellipse at 88% 10%,rgba(201,168,76,0.12),transparent 55%)'}}/>
        <div style={{position:'relative',fontFamily:'DM Sans,sans-serif',fontSize:10,
          letterSpacing:'0.22em',textTransform:'uppercase',
          color:'rgba(232,201,109,0.7)',marginBottom:8}}>
          Patrimonio Neto
        </div>
        <div style={{position:'relative',display:'flex',alignItems:'baseline',gap:12}}>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:46,
            fontWeight:600,color:GOLD,lineHeight:0.95,letterSpacing:'0.01em'}}>
            {fmt(data.patrimonio_neto)}
          </div>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:14,
            color:'rgba(232,201,109,0.55)'}}>MXN</div>
        </div>
        {data.trend_pct !== 0 && (
          <div style={{position:'relative',display:'flex',alignItems:'center',gap:6,
            marginTop:8,fontFamily:'DM Sans,sans-serif',fontSize:12,color:trendColor}}>
            {trendSymbol} {Math.abs(data.trend_pct)}%
            {data.trend_delta !== 0 && (
              <span style={{color:'rgba(242,237,224,0.4)',fontSize:11}}>
                · {data.trend_delta > 0 ? '+' : ''}{fmt(data.trend_delta)} este mes
              </span>
            )}
          </div>
        )}
        {sparkBars}
        <div style={{position:'relative',display:'flex',justifyContent:'space-between',
          marginTop:14,paddingTop:13,borderTop:'1px solid rgba(201,168,76,0.14)'}}>
          {[
            {label:'Activos', val:fmt(data.activos),  color:'#7BC49A'},
            {label:'Pasivos', val:fmt(data.pasivos),  color:'#E59B92'},
            {label:'Líquido', val:fmt(data.liquido),  color:GOLD},
          ].map((it,i) => (
            <div key={i}>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.14em',
                textTransform:'uppercase',color:'rgba(242,237,224,0.4)',marginBottom:3}}>
                {it.label}
              </div>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:17,color:it.color}}>
                {it.val}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Payment alert — gold accent, matches mockup */}
      {data.pay_alerts && data.pay_alerts.length > 0 && (
        <div style={{display:'flex',alignItems:'center',gap:11,
          background:'rgba(139,105,20,0.07)',
          border:'1px solid rgba(201,168,76,0.3)',
          borderLeft:'3px solid rgba(201,168,76,0.9)',
          borderRadius:'0 11px 11px 0',
          padding:'12px 15px',marginBottom:18}}>
          <div style={{width:30,height:30,borderRadius:8,
            background:'rgba(201,168,76,0.12)',
            display:'flex',alignItems:'center',justifyContent:'center',
            flexShrink:0,fontSize:14}}>
            🔔
          </div>
          <div style={{flex:1,fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>
            Hoy · pagar{' '}
            {data.pay_alerts.map(a => (
              <span key={a.label} style={{color:a.color,fontWeight:600,marginRight:4}}>{a.label}</span>
            ))}
          </div>
          <span style={{fontSize:14,color:'rgba(201,168,76,0.6)'}}>→</span>
        </div>
      )}

      {/* 3 pilares */}
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,letterSpacing:'0.18em',
        color:C.textMuted,textTransform:'uppercase',margin:'0 0 10px 2px'}}>Núcleo</div>
      <div style={{display:'flex',flexDirection:'column',gap:9,marginBottom:20}}>
        {pillars.map((p,i) => (
          <a key={i} href={p.href} style={{display:'flex',alignItems:'center',gap:14,
            background:C.card,border:'1px solid var(--b)',borderRadius:14,
            padding:'15px 16px',textDecoration:'none',color:'inherit',
            transition:'all 0.2s'}}>
            <div style={{width:42,height:42,borderRadius:11,flexShrink:0,
              display:'flex',alignItems:'center',justifyContent:'center',
              fontSize:19,background:p.iconBg}}>
              {p.icon}
            </div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:19,fontWeight:600,
                color:C.text,letterSpacing:'0.02em',lineHeight:1.1}}>
                {p.label}
              </div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:11,
                color:C.textMuted,marginTop:2}}>
                {p.sub}
              </div>
            </div>
            {p.statV && (
              <div style={{textAlign:'right',flexShrink:0}}>
                <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:18,
                  color:C.text,lineHeight:1}}>
                  {p.statV}
                </div>
                <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
                  letterSpacing:'0.1em',textTransform:'uppercase',
                  color:C.textMuted,marginTop:3}}>
                  {p.statL}
                </div>
              </div>
            )}
          </a>
        ))}
      </div>

      {/* Accesos */}
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,letterSpacing:'0.18em',
        color:C.textMuted,textTransform:'uppercase',margin:'0 0 10px 2px'}}>Accesos</div>
      <div style={{display:'flex',gap:8}}>
        {[
          {icon:'🛒', label:'Consumo',  href:'/finanzas/consumo'},
          {icon:'⭐', label:'Wishlist', href:'/finanzas/prioridades'},
          {icon:'✈️', label:'Viajes',   href:'/finanzas/estados/viajes'},
        ].map((chip,i) => (
          <a key={i} href={chip.href} style={{flex:1,display:'flex',flexDirection:'column',
            alignItems:'center',gap:6,background:C.card2,border:'1px solid var(--b)',
            borderRadius:12,padding:'13px 8px',textDecoration:'none',color:'inherit',
            transition:'border-color 0.2s'}}>
            <span style={{fontSize:18}}>{chip.icon}</span>
            <span style={{fontFamily:'DM Sans,sans-serif',fontSize:11,
              color:C.textMuted,letterSpacing:'0.04em'}}>{chip.label}</span>
          </a>
        ))}
      </div>
    </div>
  );
}

function HegemonikonExtra({ acc, isDesktop }) {
  const [data, setData]       = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    fetch('/bienestar/api/hegemonikon-summary')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{textAlign:'center',padding:'24px 0',fontFamily:'DM Sans,sans-serif',
      fontSize:11,color:C.textMuted,letterSpacing:'0.1em'}}>cargando…</div>
  );

  const b     = (data && data.body)        || {};
  const nut   = (data && data.nutricion)   || {comidas_done:0, comidas_total:0, streak:0, xp_today:0};
  const salud = (data && data.salud)       || {episodios_activos:0, meds_activos:0};
  const guard = (data && data.guardarropa) || {items:0, outfits:0};
  const rec   = (data && data.recetas)     || {total:0, favoritas:0};
  const futbol = (data && data.futbol)     || {partidos:0, rating:null};

  const bodyRows = [
    {label:'Peso',      val: b.peso     || '—', sub: b.estatura ? `Estatura: ${b.estatura}` : ''},
    {label:'Pecho',     val: b.pecho    || '—', sub: b.cintura ? `Cintura: ${b.cintura}` : ''},
    {label:'Hombros',   val: b.hombros  || '—', sub: b.manga   ? `Manga: ${b.manga}`    : ''},
    {label:'T. Camisa', val: b.t_camisa || '—', sub: b.t_pantalon ? `Pantalón: ${b.t_pantalon}` : ''},
  ];

  const subs = [
    { href:'/bienestar/salud', icon:'🩺', label:'Salud', hue:350,
      sub: salud.episodios_activos > 0
        ? `${salud.episodios_activos} episodio${salud.episodios_activos!==1?'s':''} activo${salud.episodios_activos!==1?'s':''}`
        : 'Al día',
      alert: salud.episodios_activos > 0 },
    { href:'/nutricion/', icon:'🥗', label:'Nutrición', hue:140,
      sub: `${nut.comidas_done}/${nut.comidas_total} comidas hoy · racha ${nut.streak}d` },
    { href:'/guardarropa/', icon:'👔', label:'Guardarropa', hue:280,
      sub: `${guard.items} prendas · ${guard.outfits} outfits` },
    { href:'/recetas/', icon:'🍳', label:'Recetas', hue:40,
      sub: `${rec.total} recetas · ${rec.favoritas} favoritas` },
    { href:'/perfil/', icon:'👤', label:'Perfil', hue:220, sub:'Datos personales · documentos' },
    { href:'/bienestar/futbol', icon:'⚽', label:'Fútbol', hue:170,
      sub: futbol.partidos > 0
        ? `${futbol.partidos} partido${futbol.partidos!==1?'s':''}${futbol.rating ? ` · rating ${futbol.rating}` : ''}`
        : 'Registra tu primer partido' },
  ];

  // ── Sparkline de peso (últimos registros, más viejo→reciente) ──────────
  const sparkPts = (data && data.peso_spark) || [];
  const pesoSpark = sparkPts.length >= 2 && (() => {
    const w = 84, h = 28, pad = 3;
    const min = Math.min(...sparkPts), max = Math.max(...sparkPts);
    const range = (max - min) || 1;
    const step = (w - pad*2) / (sparkPts.length - 1);
    const pts = sparkPts.map((v,i) => [
      pad + i*step,
      pad + (h - pad*2) * (1 - (v - min) / range),
    ]);
    const path = pts.map((p,i) => `${i===0?'M':'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
    const last = pts[pts.length - 1];
    return (
      <svg width={w} height={h} style={{flexShrink:0}}>
        <path d={path} fill="none" stroke={acc} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" opacity="0.85"/>
        <circle cx={last[0]} cy={last[1]} r="2.4" fill={acc}/>
      </svg>
    );
  })();

  const alertBanner = (salud.episodios_activos > 0 || salud.meds_activos > 0) && (
    <div style={{display:'flex',alignItems:'center',gap:11,
      background:'rgba(244,63,94,0.06)', border:'1px solid rgba(244,63,94,0.25)',
      borderLeft:'3px solid rgba(244,63,94,0.8)', borderRadius:'0 11px 11px 0',
      padding:'12px 15px', marginBottom:18}}>
      <div style={{width:30,height:30,borderRadius:8,background:'rgba(244,63,94,0.12)',
        display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0,fontSize:14}}>🩺</div>
      <div style={{flex:1,fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>
        {salud.episodios_activos} episodio{salud.episodios_activos!==1?'s':''} activo{salud.episodios_activos!==1?'s':''}
        {salud.meds_activos > 0 && ` · ${salud.meds_activos} medicamento${salud.meds_activos!==1?'s':''} en curso`}
      </div>
      <a href="/bienestar/salud" style={{fontSize:14,color:'rgba(244,63,94,0.8)',textDecoration:'none'}}>→</a>
    </div>
  );

  const bodySection = (
    <div style={{marginBottom:20}}>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Métricas Corporales</div>
      {bodyRows.map((r,i) => (
        <div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          padding:'11px 0',borderBottom:'1px solid color-mix(in srgb, var(--gold) 6%, transparent)'}}>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textSub}}>{r.label}</div>
          {r.label==='Peso' && pesoSpark}
          <div style={{textAlign:'right'}}>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:19,color:acc,
              display:'flex',alignItems:'baseline',gap:6,justifyContent:'flex-end'}}>
              {r.val}
              {r.label==='Peso' && data && data.peso_trend != null && data.peso_trend !== 0 && (
                <span style={{fontFamily:'DM Sans,sans-serif',fontSize:10,
                  color: data.peso_trend < 0 ? '#7BC49A' : '#E59B92'}}>
                  {data.peso_trend < 0 ? '▼' : '▲'} {Math.abs(data.peso_trend)}
                </span>
              )}
            </div>
            {r.sub && <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>{r.sub}</div>}
          </div>
        </div>
      ))}
    </div>
  );

  const subsSection = (
    <div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Submódulos</div>
      {subs.map((s,i) => {
        const tintBg     = EU.catTint(s.hue, 'bg');
        const tintBorder = EU.catTint(s.hue, 'border');
        const tintText   = EU.catTint(s.hue, 'text');
        return (
          <a key={i} href={s.href} style={{
              display:'flex', justifyContent:'space-between', alignItems:'center',
              background:C.card, border:`1px solid ${s.alert ? 'rgba(244,63,94,0.4)' : 'var(--gold-border)'}`,
              borderRadius:12, padding:'12px 14px', marginBottom:8,
              textDecoration:'none', transform:'scale(1)',
              transition:'border-color 0.18s, transform 0.18s, box-shadow 0.18s',
              animation:`eu-fade-in 0.3s ease ${i*0.04}s both`}}
            onMouseEnter={e=>{
              e.currentTarget.style.borderColor = s.alert ? 'rgba(244,63,94,0.4)' : tintBorder;
              e.currentTarget.style.transform = 'scale(1.015)';
              e.currentTarget.style.boxShadow = `0 4px 16px ${tintBg}`;
            }}
            onMouseLeave={e=>{
              e.currentTarget.style.borderColor = s.alert ? 'rgba(244,63,94,0.4)' : 'var(--gold-border)';
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.boxShadow = 'none';
            }}>
            <div style={{display:'flex',alignItems:'center',gap:11}}>
              <div style={{width:34,height:34,borderRadius:10,flexShrink:0,background:tintBg,
                display:'flex',alignItems:'center',justifyContent:'center',fontSize:16}}>{s.icon}</div>
              <div>
                <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>{s.label}</div>
                <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,
                  color: s.alert ? '#E59B92' : C.textMuted, marginTop:1}}>{s.sub}</div>
              </div>
            </div>
            <span style={{color: tintText, fontSize:15, opacity:0.7}}>›</span>
          </a>
        );
      })}
    </div>
  );

  const fadeKeyframes = (
    <style>{`@keyframes eu-fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }`}</style>
  );

  if (isDesktop) {
    return (
      <div style={{display:'grid',gridTemplateColumns:'1fr 340px',gap:'0 28px',alignItems:'start'}}>
        {fadeKeyframes}
        <div>
          {alertBanner}
          {bodySection}
        </div>
        <div style={{position:'sticky',top:24}}>
          {subsSection}
        </div>
      </div>
    );
  }

  return (
    <div>
      {fadeKeyframes}
      {alertBanner}
      {subsSection}
      {bodySection}
    </div>
  );
}

function PaideiaExtra({ acc }) {
  const [data, setData]       = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [tip, setTip]         = React.useState(null);
  const [tipSpin, setTipSpin] = React.useState(false);

  React.useEffect(() => {
    fetch('/paideia/api/summary')
      .then(r => r.json())
      .then(d => { setData(d); setTip(d.tip); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const refreshTip = (e) => {
    e.preventDefault();
    setTipSpin(true);
    fetch('/paideia/api/tip/refresh')
      .then(r => r.json())
      .then(t => { setTip(t); setTipSpin(false); })
      .catch(() => setTipSpin(false));
  };

  if (loading) return (
    <div style={{textAlign:'center',padding:'24px 0',fontFamily:'DM Sans,sans-serif',
      fontSize:11,color:C.textMuted,letterSpacing:'0.1em'}}>cargando…</div>
  );

  const stats = (data && data.stats) || {meta_anual:12, leidos_este_anio:0, total_leidos:0, leyendo:0, por_leer:0, rating_prom:null};
  const leyendo = data && data.leyendo;
  const pct = stats.meta_anual > 0 ? Math.min(100, (stats.leidos_este_anio / stats.meta_anual) * 100) : 0;

  return (
    <div>
      <style>{`@keyframes eu-fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }`}</style>

      {/* Meta de lectura */}
      <a href="/paideia/" style={{display:'block',textDecoration:'none',
        background:`linear-gradient(135deg, ${acc}, color-mix(in srgb, ${acc} 60%, white))`,
        borderRadius:16, padding:'16px 18px', marginBottom:16, animation:'eu-fade-in 0.3s ease both'}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,fontWeight:600,color:'rgba(9,7,15,0.65)',
          textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:6}}>Meta de lectura</div>
        <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:26,fontWeight:700,color:'#09070F',marginBottom:10}}>
          {stats.leidos_este_anio} / {stats.meta_anual} libros
        </div>
        <div style={{height:6,borderRadius:3,background:'rgba(9,7,15,0.15)',overflow:'hidden'}}>
          <div style={{height:'100%',borderRadius:3,background:'#09070F',width:`${pct}%`,transition:'width 0.6s ease'}}/>
        </div>
      </a>

      {/* Leyendo ahora */}
      {leyendo && (
        <a href="/paideia/" style={{display:'block',textDecoration:'none',background:C.card,
          border:'1px solid var(--gold-border)',borderRadius:14,padding:'14px 16px',marginBottom:16,
          animation:'eu-fade-in 0.3s ease 0.05s both'}}>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.12em',
            color:C.textMuted,textTransform:'uppercase',marginBottom:8}}>Leyendo ahora</div>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:14,fontWeight:600,color:C.text}}>{leyendo.titulo}</div>
          {leyendo.autor && <div style={{fontFamily:'DM Sans,sans-serif',fontSize:11,color:C.textMuted,marginTop:1}}>{leyendo.autor}</div>}
          {leyendo.paginas_totales > 0 && (
            <div style={{height:4,borderRadius:2,background:'var(--gold-bg, rgba(201,168,76,0.15))',overflow:'hidden',marginTop:9}}>
              <div style={{height:'100%',borderRadius:2,background:acc,
                width:`${Math.min(100, (leyendo.paginas_actuales / leyendo.paginas_totales) * 100)}%`}}/>
            </div>
          )}
        </a>
      )}

      {/* Tip de conocimiento */}
      {tip && (
        <div style={{display:'flex',alignItems:'flex-start',gap:10,background:C.card,
          border:'1px solid var(--gold-border)',borderRadius:14,padding:'14px 16px',marginBottom:16,
          animation:'eu-fade-in 0.3s ease 0.1s both'}}>
          <span style={{fontSize:18,flexShrink:0}}>{tip.icon}</span>
          <div style={{flex:1,fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.text,lineHeight:1.5}}>{tip.text}</div>
          <button onClick={refreshTip} title="Otro tip" style={{background:'none',border:'none',cursor:'pointer',
            color:C.textMuted,fontSize:14,flexShrink:0,transform:tipSpin?'rotate(180deg)':'none',transition:'transform 0.3s'}}>↻</button>
        </div>
      )}

      {/* Submódulos */}
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Submódulos</div>
      <a href="/paideia/" style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          background:C.card,border:'1px solid var(--gold-border)',borderRadius:12,
          padding:'12px 14px',textDecoration:'none',transition:'border-color 0.18s, transform 0.18s',
          animation:'eu-fade-in 0.3s ease 0.15s both'}}
        onMouseEnter={e=>{e.currentTarget.style.borderColor=acc; e.currentTarget.style.transform='scale(1.01)';}}
        onMouseLeave={e=>{e.currentTarget.style.borderColor='var(--gold-border)'; e.currentTarget.style.transform='scale(1)';}}>
        <div style={{display:'flex',alignItems:'center',gap:11}}>
          <div style={{width:34,height:34,borderRadius:10,flexShrink:0,background:EU.catTint(265,'bg'),
            display:'flex',alignItems:'center',justifyContent:'center',fontSize:16}}>📚</div>
          <div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>Libros</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.textMuted,marginTop:1}}>
              {stats.total_leidos} leídos · {stats.leyendo} leyendo · {stats.por_leer} por leer
            </div>
          </div>
        </div>
        <span style={{color:EU.catTint(265,'text'),fontSize:15,opacity:0.7}}>›</span>
      </a>
    </div>
  );
}

function ModuleExtra({ id, acc, isDesktop }) {
  const srv = (window.EU._server) || {};

  if (id === 'oikonomia') return <OikonomiaExtra />;

  if (id === 'cosmopolitismo') {
    const langs = (srv.langStats && srv.langStats.length)
      ? srv.langStats
      : [{lang:'Alemán',lvl:'B1+',entries:0,pct:0.72},{lang:'Inglés',lvl:'C1',entries:0,pct:0.91},{lang:'Francés',lvl:'A2',entries:0,pct:0.25}];
    return (
      <div>
        {/* Acceso directo */}
        <a href="/idiomas/" style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          background:C.card,border:'1px solid var(--gold-border)',borderRadius:12,
          padding:'11px 14px',marginBottom:18,textDecoration:'none',transition:'border-color 0.18s'}}
          onMouseEnter={e=>e.currentTarget.style.borderColor=acc}
          onMouseLeave={e=>e.currentTarget.style.borderColor='var(--gold-border)'}>
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <span style={{fontSize:18}}>🌍</span>
            <div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>Cosmopolitismo</div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.textMuted,marginTop:1}}>Lecciones · Vocabulario · Práctica</div>
            </div>
          </div>
          <span style={{color:C.textMuted,fontSize:14}}>›</span>
        </a>
        {/* Progreso */}
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',marginBottom:14}}>Idiomas en Progreso</div>
        {langs.map((l,i) => (
          <div key={i} style={{marginBottom:16}}>
            <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
              <span style={{fontFamily:'Cormorant Garamond,serif',fontSize:17,color:C.text}}>{l.lang}</span>
              <span style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:acc}}>
                {l.lvl}{l.entries ? ` · ${l.entries} entradas` : ''}
              </span>
            </div>
            <div style={{height:3,background:'var(--gold-bg)',borderRadius:2}}>
              <div style={{height:'100%',borderRadius:2,background:acc,
                width:`${(l.pct||0)*100}%`,boxShadow:`0 0 6px ${acc}66`}}/>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (id === 'hegemonikon') return <HegemonikonExtra acc={acc} isDesktop={isDesktop}/>;

  if (id === 'paideia') return <PaideiaExtra acc={acc} isDesktop={isDesktop}/>;

  if (id === 'ataraxia') {
    const mkLink = (href, icon, label, sub) => (
      <a href={href} style={{display:'flex',justifyContent:'space-between',alignItems:'center',
        background:C.card,border:'1px solid var(--gold-border)',borderRadius:12,
        padding:'11px 14px',marginBottom:8,textDecoration:'none',transition:'border-color 0.18s'}}
        onMouseEnter={e=>e.currentTarget.style.borderColor=acc}
        onMouseLeave={e=>e.currentTarget.style.borderColor='var(--gold-border)'}>
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <span style={{fontSize:18}}>{icon}</span>
          <div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>{label}</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.textMuted,marginTop:1}}>{sub}</div>
          </div>
        </div>
        <span style={{color:C.textMuted,fontSize:14}}>›</span>
      </a>
    );
    return (
      <div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Submódulos</div>
        {mkLink('/ataraxia/',  '⚓', 'Ataraxia',      'Checklist semanal · Orden')}
        {mkLink('/gtd/',       '🎯', 'Praxis GTD',    'Inbox · Next Actions · Proyectos')}
      </div>
    );
  }

  if (id === 'logoi') {
    return (
      <div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Submódulos</div>
        <a href="/actividades" style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          background:C.card,border:'1px solid var(--gold-border)',borderRadius:12,
          padding:'11px 14px',marginBottom:8,textDecoration:'none',transition:'border-color 0.18s'}}
          onMouseEnter={e=>e.currentTarget.style.borderColor=acc}
          onMouseLeave={e=>e.currentTarget.style.borderColor='var(--gold-border)'}>
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <span style={{fontSize:18}}>💻</span>
            <div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>Acta Diurna</div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.textMuted,marginTop:1}}>Programación · Lógica · Proyectos</div>
            </div>
          </div>
          <span style={{color:C.textMuted,fontSize:14}}>›</span>
        </a>
      </div>
    );
  }

  if (id === 'eurythmia') {
    return (
      <div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Submódulos</div>
        <a href="/actividades" style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          background:C.card,border:'1px solid var(--gold-border)',borderRadius:12,
          padding:'11px 14px',marginBottom:8,textDecoration:'none',transition:'border-color 0.18s'}}
          onMouseEnter={e=>e.currentTarget.style.borderColor=acc}
          onMouseLeave={e=>e.currentTarget.style.borderColor='var(--gold-border)'}>
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            <span style={{fontSize:18}}>🕺</span>
            <div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>Acta Diurna</div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.textMuted,marginTop:1}}>Baile · Ritmo · Práctica</div>
            </div>
          </div>
          <span style={{color:C.textMuted,fontSize:14}}>›</span>
        </a>
      </div>
    );
  }

  return null;
}

// ═══════════════════════════════════════════════════════════
// PRAXIS INBOX — GTD tabs (extracted, not yet wired to Acta)
// ═══════════════════════════════════════════════════════════
function PraxisInbox({ isDesktop }) {
  const [gtdTab, setGtdTab] = useState('inbox');
  const [inbox, setInbox]   = useState(EU.gtd.inbox);
  const [newItem, setNewItem] = useState('');
  const [inputFocus, setInputFocus] = useState(false);

  const addItem = () => {
    if (!newItem.trim()) return;
    setInbox(p => [...p, {id:Date.now(), text:newItem.trim(), context:'@inbox'}]);
    setNewItem('');
  };

  const GTD_TABS = [
    {id:'inbox',    label:'Inbox',     count: inbox.length},
    {id:'projects', label:'Proyectos', count: EU.gtd.projects.length},
    {id:'contexts', label:'Contextos'},
    {id:'review',   label:'Revisión'},
  ];

  return (
    <div style={{borderTop:'1px solid var(--gold-bg)', marginTop:4}}>
      <div style={{
        display:'flex', borderBottom:'1px solid var(--gold-bg)',
        padding: isDesktop ? '0 24px' : '0 20px',
      }}>
        {GTD_TABS.map(t => (
          <div key={t.id} onClick={() => setGtdTab(t.id)} style={{
            flex:1, padding:'11px 2px', textAlign:'center', cursor:'pointer',
            fontFamily:'DM Sans,sans-serif', fontSize:11, fontWeight: gtdTab===t.id?700:400,
            color: gtdTab===t.id ? C.gold : C.textMuted,
            borderBottom: gtdTab===t.id ? `2px solid ${C.gold}` : '2px solid transparent',
            transition:'all 0.2s',
          }}>{t.label}{t.count != null && (
            <span style={{marginLeft:5,fontSize:9,borderRadius:9,padding:'1px 6px',
              background: gtdTab===t.id ? C.gold : 'rgba(201,168,76,0.14)',
              color: gtdTab===t.id ? C.deep : C.textSub}}>{t.count}</span>
          )}</div>
        ))}
      </div>

      <div style={{padding: isDesktop ? '16px 24px 0' : '16px 20px 0'}}>
        {gtdTab === 'inbox' && (
          <div>
            <div style={{display:'flex',gap:8,marginBottom:14,
              background:C.card,border:`1.5px solid ${inputFocus?C.gold:'var(--b)'}`,
              borderRadius:10,padding:'4px 4px 4px 14px',alignItems:'center',
              boxShadow: inputFocus?'0 0 0 3px rgba(201,168,76,0.12)':'none',transition:'all 0.15s'}}>
              <input value={newItem} onChange={e=>setNewItem(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&addItem()}
                onFocus={()=>setInputFocus(true)} onBlur={()=>setInputFocus(false)}
                placeholder="Capturar pensamiento..."
                style={{flex:1,background:'none',border:'none',outline:'none',
                  fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}/>
              <button onClick={addItem} style={{
                background:C.gold,border:'none',borderRadius:7,width:34,height:34,cursor:'pointer',
                fontFamily:'DM Sans,sans-serif',fontSize:20,color:C.deep,
                display:'flex',alignItems:'center',justifyContent:'center',lineHeight:1}}>+</button>
            </div>
            {inbox.length === 0
              ? <div style={{textAlign:'center',padding:'40px 0',
                  fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
                  fontSize:17,color:C.textMuted}}>Inbox limpio. Mente clara.</div>
              : inbox.map(item => (
                <div key={item.id} style={{display:'flex',alignItems:'center',gap:10,
                  padding:'11px 0',borderBottom:'1px solid color-mix(in srgb, var(--gold) 6%, transparent)'}}>
                  <div style={{width:5,height:5,borderRadius:'50%',
                    background:'color-mix(in srgb, var(--gold) 28%, transparent)',flexShrink:0}}/>
                  <div style={{flex:1,fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>{item.text}</div>
                  <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>{item.context}</div>
                  <button onClick={()=>setInbox(p=>p.filter(i=>i.id!==item.id))}
                    style={{background:'none',border:'none',color:C.textMuted,
                      cursor:'pointer',fontSize:18,padding:'0 2px',lineHeight:1}}>×</button>
                </div>
              ))
            }
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted,
              textAlign:'center',marginTop:10}}>{inbox.length} elemento{inbox.length!==1?'s':''}</div>
          </div>
        )}

        {gtdTab === 'projects' && EU.gtd.projects.map(p => {
          const pct = p.done / p.actions;
          return (
            <div key={p.id} style={{background:C.card,border:'1px solid var(--gold-bg)',
              borderRadius:12,padding:'14px 16px',marginBottom:9}}>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text,marginBottom:9}}>{p.name}</div>
              <div style={{display:'flex',alignItems:'center',gap:10}}>
                <div style={{flex:1,height:3,background:'var(--gold-bg)',borderRadius:2}}>
                  <div style={{height:'100%',borderRadius:2,background:C.gold,
                    width:`${pct*100}%`,boxShadow:'0 0 6px var(--gold-glow)'}}/>
                </div>
                <span style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.textMuted,
                  whiteSpace:'nowrap'}}>{p.done}/{p.actions}</span>
              </div>
            </div>
          );
        })}

        {gtdTab === 'contexts' && (
          <div style={{display:'flex',flexWrap:'wrap',gap:8,paddingTop:4}}>
            {EU.gtd.contexts.map(ctx => (
              <div key={ctx} style={{padding:'8px 14px',
                background:C.card,border:'1px solid color-mix(in srgb, var(--gold) 12%, transparent)',
                borderRadius:20,fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textSub}}>
                {ctx}
              </div>
            ))}
          </div>
        )}

        {gtdTab === 'review' && (
          <div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
              fontSize:15,color:C.textSub,lineHeight:1.65,marginBottom:18,textWrap:'pretty'}}>
              "La revisión semanal es el mantenimiento del sistema. Sin ella, el GTD colapsa."
            </div>
            {EU.gtd.review.map((item,i) => (
              <div key={i} style={{display:'flex',alignItems:'center',gap:12,
                padding:'10px 0',borderBottom:'1px solid color-mix(in srgb, var(--gold) 6%, transparent)'}}>
                <div style={{
                  width:20,height:20,borderRadius:6,flexShrink:0,
                  border:`1.5px solid ${item.done?C.gold:'color-mix(in srgb, var(--gold) 20%, transparent)'}`,
                  background:item.done?C.gold:'transparent',
                  display:'flex',alignItems:'center',justifyContent:'center',
                }}>
                  {item.done && <svg width={10} height={10} viewBox="0 0 10 10">
                    <polyline points="2,5 4.5,8 8,2" stroke={C.deep} strokeWidth={1.5}
                      fill="none" strokeLinecap="round"/>
                  </svg>}
                </div>
                <span style={{fontFamily:'DM Sans,sans-serif',fontSize:13,
                  color:item.done?C.textMuted:C.text,
                  textDecoration:item.done?'line-through':'none'}}>{item.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// UNDO TOAST
// ═══════════════════════════════════════════════════════════
function useUndoToast() {
  const [toast, setToast] = useState(null); // {key, logId, label, pts, id}
  const timer = useRef(null);

  const show = (key, logId, label, pts) => {
    if (timer.current) clearTimeout(timer.current);
    setToast({key, logId, label, pts, id: Date.now()});
    timer.current = setTimeout(() => setToast(null), 5000);
  };

  const dismiss = () => {
    if (timer.current) clearTimeout(timer.current);
    setToast(null);
  };

  return { toast, show, dismiss };
}

function UndoToast({ toast, onUndo, onDismiss, isDesktop }) {
  if (!toast) return null;
  return (
    <div style={{
      position:'fixed',
      bottom: isDesktop ? 24 : 88,
      left:'50%', transform:'translateX(-50%)',
      zIndex:9999,
      background: C.card,
      border:'1px solid color-mix(in srgb, var(--gold) 25%, transparent)',
      borderRadius:12,
      padding:'12px 16px',
      boxShadow:'0 8px 32px rgba(0,0,0,0.55)',
      display:'flex', alignItems:'center', gap:12,
      minWidth:240, maxWidth:'calc(100vw - 32px)',
      animation:'euScaleIn 0.2s ease',
    }}>
      {/* Text */}
      <div style={{flex:1}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.text,lineHeight:1.3}}>
          {toast.label}
        </div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.gold,marginTop:2}}>
          +{toast.pts} XP registrado
        </div>
      </div>
      {/* Undo button */}
      <button onClick={onUndo} style={{
        background:'transparent',
        border:'1px solid var(--b2)',
        borderRadius:6, padding:'5px 12px',
        fontFamily:'DM Sans,sans-serif', fontSize:11,
        color:C.gold, cursor:'pointer', letterSpacing:'0.06em',
        textTransform:'uppercase', flexShrink:0,
        transition:'all 0.15s',
      }}>Deshacer</button>
      {/* Dismiss */}
      <button onClick={onDismiss} style={{
        background:'none', border:'none',
        color:C.textMuted, cursor:'pointer',
        fontSize:16, padding:'0 2px', lineHeight:1,
      }}>×</button>
      {/* 5s countdown bar — CSS animation keyed to toast.id */}
      <div key={toast.id} style={{
        position:'absolute', bottom:0, left:0,
        height:3, borderRadius:'0 0 12px 12px',
        background:`linear-gradient(90deg,${C.gold},${C.goldLight})`,
        animation:'undoCountdown 5s linear forwards',
        width:'100%',
      }}/>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// ACTIVITY BUTTON
// ═══════════════════════════════════════════════════════════
function ActivityButton({ act, catHue, onLog }) {
  const { isLight } = useTheme();
  const [burst, setBurst] = useState(false);
  const isAlto = act.tier === 'alto';

  const handle = () => {
    if (!act.done) {
      setBurst(true);
      setTimeout(() => setBurst(false), 700);
    }
    onLog(act.key);
  };

  const dirs = [[26,-26],[36,0],[26,26],[0,34],[-26,26],[-36,0],[-26,-26],[0,-34]];
  const burstColor = isAlto ? '#fbbf24' : EU.catTint(catHue, 'text');

  return (
    <div onClick={handle} style={{
      display:'flex', flexDirection:'column',
      padding:'10px 12px', borderRadius:10, cursor:'pointer',
      background: act.done
        ? (isAlto ? 'rgba(245,158,11,0.07)' : 'rgba(99,102,241,0.07)')
        : C.card,
      border: act.done
        ? (isAlto ? '1px solid rgba(245,158,11,0.3)' : '1px solid rgba(99,102,241,0.25)')
        : `1px solid ${EU.catTint(catHue, 'border')}`,
      minHeight:52, gap:5,
      transition:'all 0.18s',
      position:'relative', overflow:'hidden',
    }}>
      {/* ALTO IMPACTO ribbon */}
      {isAlto && (
        <div style={{
          position:'absolute', top:0, right:0,
          background: act.done ? 'rgba(245,158,11,0.35)' : 'rgba(245,158,11,0.14)',
          color: '#fbbf24',
          fontSize:7, letterSpacing:'0.1em', textTransform:'uppercase',
          padding:'2px 7px',
          borderRadius:'0 10px 0 6px',
          transition:'background 0.2s',
        }}>ALTO</div>
      )}
      {/* Checkbox row */}
      <div style={{display:'flex',alignItems:'center',gap:8}}>
        <div style={{
          width:16, height:16, borderRadius:5, flexShrink:0,
          border:`1.5px solid ${act.done
            ? (isAlto ? '#fbbf24' : 'rgba(99,102,241,0.7)')
            : EU.catTint(catHue, 'border')}`,
          background: act.done
            ? (isAlto ? '#fbbf24' : 'rgba(99,102,241,0.8)')
            : 'transparent',
          display:'flex', alignItems:'center', justifyContent:'center',
          transition:'all 0.2s',
          boxShadow: act.done
            ? (isAlto ? '0 0 8px rgba(245,158,11,0.4)' : '0 0 8px rgba(99,102,241,0.35)')
            : 'none',
        }}>
          {act.done && (
            <svg width={9} height={9} viewBox="0 0 9 9">
              <polyline points="1.5,4.5 3.7,7 7.5,1.5"
                stroke={isAlto ? '#1a1210' : '#fff'}
                strokeWidth={1.6} fill="none" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </div>
        <span style={{
          fontFamily:'DM Sans,sans-serif', fontSize:11,
          color: act.done ? C.textMuted : C.textSub,
          fontWeight: act.done ? 500 : 400,
          lineHeight:1.3, flex:1,
          textDecoration: act.done ? 'none' : 'none',
        }}>{act.label}</span>
      </div>
      {/* XP + EC row */}
      <div style={{display:'flex',justifyContent:'flex-end',alignItems:'center',gap:4}}>
        <span style={{
          fontFamily:'DM Sans,sans-serif', fontSize:9,
          padding:'1px 6px', borderRadius:100,
          background: act.done
            ? (isAlto
                ? 'linear-gradient(135deg,rgba(245,158,11,0.5),rgba(234,179,8,0.5))'
                : 'linear-gradient(135deg,rgba(99,102,241,0.7),rgba(139,92,246,0.7))')
            : EU.catTint(catHue, 'bg'),
          color: act.done ? '#fff' : EU.catTint(catHue, 'text'),
          border: act.done ? 'none' : `1px solid ${EU.catTint(catHue, 'border')}`,
        }}>+{act.pts} XP{act.ec > 0 ? ` · ${act.ec}🪙` : ''}</span>
      </div>
      {/* Burst particles */}
      {burst && dirs.map(([dx,dy],i) => (
        <div key={i} style={{
          position:'absolute', left:'50%', top:'50%',
          width:5, height:5, borderRadius:'50%',
          background:burstColor,
          transform:`translate(${dx}px,${dy}px)`,
          opacity:0, animation:'euBurst 0.65s ease-out forwards',
          animationDelay:`${i*0.025}s`, pointerEvents:'none',
        }}/>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// ACTA DIURNA SCREEN
// ═══════════════════════════════════════════════════════════
function ActaDiurnaScreen({ appState, dispatch, isDesktop }) {
  const srv = window.EU._server || {};
  const [acts, setActs] = useState(srv.activities || []);
  const [pts,  setPts]  = useState(srv.pts || {today:0, week:0, month:0});
  const [streak, setStreak] = useState(srv.streak || 0);
  const actCats = srv.actCats || [];
  const { level, xp, xpNext } = appState;
  const [xpToday, setXpToday] = useState(srv.xpToday || 0);
  const [clf, setClf]          = useState(srv.classification || {});
  const [loaded, setLoaded]    = useState(!!(srv.activities && srv.activities.length > 0));
  const XP_GOAL   = 15;
  const xpDayPct  = Math.min(1, xpToday / XP_GOAL);

  useEffect(() => {
    fetch('/actividades/api/today')
      .then(r => r.json())
      .then(data => {
        if (data.activities) {
          setActs(data.activities);
          window.EU._server.activities = data.activities;
        }
        // /api/today devuelve data.xp (no data.pts)
        if (data.xp) {
          const newPts = {today: data.xp.today, week: data.xp.week, month: data.xp.month};
          setPts(newPts);
          window.EU._server.pts = newPts;
          setXpToday(data.xp.today);
          window.EU._server.xpToday = data.xp.today;
        }
        if (data.streak !== undefined) {
          setStreak(data.streak);
          window.EU._server.streak = data.streak;
        }
        if (data.classification) {
          setClf(data.classification);
          window.EU._server.classification = data.classification;
        }
        setLoaded(true);
      })
      .catch(() => { setLoaded(true); });
  }, []);

  const logActivity = (key) => {
    const source  = window.EU._server.activities || acts;
    const act     = source.find(a => a.key === key);
    const updated = source.map(a => a.key === key ? {...a, done: !a.done} : a);
    window.EU._server.activities = updated;
    setActs(updated);

    fetch('/actividades/api/activity/log', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({key}),
    })
    .then(r => r.json())
    .then(data => {
      if (data.stats) {
        const newXp = data.stats.xp_today ?? data.stats.pts_today ?? xpToday;
        setXpToday(newXp);
        window.EU._server.xpToday = newXp;
        const newPts = {today: data.stats.pts_today, week: data.stats.pts_week, month: data.stats.pts_month};
        setPts(newPts);
        window.EU._server.pts = newPts;
        if (data.stats.streak !== undefined) {
          setStreak(data.stats.streak);
          window.EU._server.streak = data.stats.streak;
        }
      }
      if (data.gam && (data.gam.xp_delta || data.gam.xp)) dispatch({type:'ADD_XP', amount: data.gam.xp_delta || data.gam.xp});
      if (data.gam?.achievements?.length) window.euFireAchievements(data.gam.achievements);
      if (data.gam?.perfect_day) {
        window.dispatchEvent(new CustomEvent('eu:perfect-day', {
          detail: { bonusXp: data.gam.perfect_day.xp || 5, bonusEc: data.gam.perfect_day.ec || 10 }
        }));
      } else if (data.gam?.combo_bonuses?.length) {
        data.gam.combo_bonuses.forEach(c =>
          window.dispatchEvent(new CustomEvent('eu:combo-bonus', { detail: c }))
        );
      }
      if (data.action === 'added' && data.log_id && act) {
        undoToast.show(key, data.log_id, act.label, act.pts);
      } else {
        undoToast.dismiss();
      }
    })
    .catch(() => {});
  };

  const undoToast = useUndoToast();

  const handleUndo = () => {
    const t = undoToast.toast;
    if (!t) return;
    const source = window.EU._server.activities || acts;
    const restored = source.map(a => a.key === t.key ? {...a, done: false} : a);
    window.EU._server.activities = restored;
    setActs(restored);
    fetch(`/actividades/api/activity/undo/${t.logId}`, {method:'POST'})
      .then(r => r.json())
      .then(data => {
        if (data.stats) {
          const newXp = data.stats.xp_today ?? data.stats.pts_today ?? xpToday;
          setXpToday(newXp);
          window.EU._server.xpToday = newXp;
          const newPts = {today: data.stats.pts_today, week: data.stats.pts_week, month: data.stats.pts_month};
          setPts(newPts);
          window.EU._server.pts = newPts;
        }
        if (data.gam && data.gam.xp_delta) dispatch({type:'ADD_XP', amount: data.gam.xp_delta});
      })
      .catch(() => {});
    undoToast.dismiss();
  };

  if (!loaded) {
    return (
      <div style={{padding: isDesktop ? '28px 24px' : '16px 20px'}}>
        <Skeleton kind="card" height={180}/>
        <Skeleton kind="card" height={60}  style={{marginTop:12}}/>
        {[1,2,3].map(i => <Skeleton key={i} kind="card" height={200} style={{marginTop:12}}/>)}
      </div>
    );
  }

  const byCategory = {};
  actCats.forEach(cat => { byCategory[cat] = []; });
  acts.forEach(a => {
    if (byCategory[a.cat]) byCategory[a.cat].push(a);
    else { byCategory[a.cat] = [a]; }
  });

  return (
    <div style={{minHeight:'100vh', paddingBottom: isDesktop ? 48 : 100}}>

      {/* ── HERO ACTA ── */}
      <div style={{padding: isDesktop ? '28px 24px 20px' : '16px 20px 16px'}}>
        <div style={{
          background:'linear-gradient(140deg, var(--surf), var(--bg))',
          border:'1px solid var(--gold-border)',
          borderRadius:16, padding:'20px', marginBottom:14,
          position:'relative', overflow:'hidden',
        }}>
          {/* Header row: label + clf chip */}
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:6}}>
            <div style={{fontSize:9,letterSpacing:'0.18em',color:C.gold,
              opacity:0.6,textTransform:'uppercase'}}>Acta Diurna · XP hoy</div>
            {clf.rank && (() => {
              const curTier = TIERS.find(t=>t.rank===clf.rank) || TIERS[0];
              const CurIcon = curTier.Icon;
              return (
                <div style={{display:'flex',alignItems:'center',gap:5,
                  background:'rgba(255,255,255,0.05)',borderRadius:20,padding:'3px 10px'}}>
                  <CurIcon size={12} style={{color:curTier.color}}/>
                  <span style={{fontSize:9,color:C.textMuted,letterSpacing:'0.08em',
                    textTransform:'uppercase'}}>{curTier.label}</span>
                </div>
              );
            })()}
          </div>
          {/* XP numeral */}
          <div style={{display:'flex',alignItems:'baseline',gap:8,marginBottom:12}}>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:64,
              lineHeight:1,color:C.goldLight,fontWeight:600}}>{xpToday}</div>
            <div style={{fontSize:13,color:C.textMuted}}>/ {XP_GOAL} meta</div>
          </div>
          {/* Progress bar */}
          <div style={{height:5,background:'var(--gold-bg)',borderRadius:3,overflow:'hidden',marginBottom:12}}>
            <div style={{
              height:'100%',borderRadius:3,
              background:'linear-gradient(90deg, color-mix(in srgb, var(--gold) 60%, #000), var(--gold), var(--gold-l))',
              width:`${xpDayPct*100}%`,
              boxShadow:'0 0 8px var(--gold-glow)',
              transition:'width 0.8s ease',
            }}/>
          </div>
          {/* Tier ladder */}
          {(() => {
            const curIdx = TIERS.findIndex(t => t.rank === clf.rank);
            const ci = curIdx >= 0 ? curIdx : 0;
            const nt = TIERS[ci + 1] || null;
            const col = TIERS[ci].color;
            return (
              <>
                <div style={{display:'flex',alignItems:'flex-start',marginBottom:8}}>
                  {TIERS.map((t, i) => {
                    const active = i === ci;
                    const past   = i < ci;
                    const TIcon  = t.Icon;
                    return (
                      <React.Fragment key={t.rank}>
                        <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:4,flex:1}}>
                          <div style={{
                            width:active?9:5, height:active?9:5, borderRadius:'50%',
                            background:active ? col : past ? `${col}55` : 'rgba(255,255,255,0.08)',
                            boxShadow:active ? `0 0 9px ${col}` : 'none',
                            transition:'all 0.3s',
                          }}/>
                          <TIcon size={9} style={{
                            color:active ? col : C.textMuted,
                            opacity:active ? 1 : past ? 0.55 : 0.28,
                          }}/>
                          <div style={{
                            fontFamily:'DM Sans,sans-serif', fontSize:7,
                            color:active ? col : C.textMuted,
                            opacity:active ? 1 : past ? 0.55 : 0.28,
                            textAlign:'center', lineHeight:1.3,
                          }}>{t.label}</div>
                        </div>
                        {i < TIERS.length - 1 && (
                          <div style={{height:1,flex:1,marginTop:4,
                            background:i < ci ? `${col}35` : 'rgba(255,255,255,0.06)'}}/>
                        )}
                      </React.Fragment>
                    );
                  })}
                </div>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',fontSize:10}}>
                  <span style={{color:C.textMuted}}>
                    {nt ? `${Math.max(0,nt.threshold - xpToday)} XP → ${nt.label}` : '✦ Diamante alcanzado'}
                  </span>
                  <span style={{color:C.gold,opacity:0.7}}>
                    {xpNext ? `${xpNext - xp} XP → ${EU.levels[level]?.name || ''}` : ''}
                  </span>
                </div>
              </>
            );
          })()}
        </div>

        {/* ── SECONDARY STATS ── */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:8,marginBottom:16}}>
          {[
            {label:'SEMANA', val: pts.week,                   sub:'meta 50+'},
            {label:'MES',    val: pts.month,                  sub:'meta 300+'},
            {label:'RACHA',  val: streak > 0 ? `${streak}d` : '—', sub:'días'},
          ].map(s => (
            <div key={s.label} style={{
              background:C.card, border:'1px solid var(--gold-bg)',
              borderRadius:10, padding:'10px 8px',
            }}>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:7,letterSpacing:'0.1em',
                color:C.textMuted,textTransform:'uppercase',marginBottom:2}}>{s.label}</div>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:20,color:C.gold,lineHeight:1}}>{s.val}</div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:8,color:C.textMuted,marginTop:2}}>{s.sub}</div>
            </div>
          ))}
        </div>

        {/* ── ACTIVITIES BY CATEGORY — Sprint-2 blocks ── */}
        {(actCats.length > 0 ? actCats : Object.keys(byCategory)).map(cat => {
          const catActs  = byCategory[cat] || [];
          if (!catActs.length) return null;
          const catHue   = (EU.catHues || {})[cat] || 45;
          const doneCnt  = catActs.filter(a => a.done).length;
          const total    = catActs.length;
          const pct      = total > 0 ? doneCnt / total : 0;
          const complete = doneCnt === total && total > 0;
          return (
            <div key={cat} data-cat={cat} style={{
              background:EU.catTint(catHue, 'bg'),
              border:`1px solid ${complete ? EU.catTint(catHue, 'border') : 'var(--b)'}`,
              borderRadius:14, padding:'14px', marginBottom:14,
              transition:'border-color 0.3s',
            }}>
              {/* Header: dot · name · X/Y */}
              <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
                <div style={{
                  width:7, height:7, borderRadius:'50%', flexShrink:0,
                  background: doneCnt > 0 ? EU.catTint(catHue, 'text') : 'var(--b2)',
                  boxShadow: doneCnt > 0 ? `0 0 6px ${EU.catTint(catHue, 'text')}` : 'none',
                  transition:'all 0.3s',
                }}/>
                <span style={{
                  fontFamily:'DM Sans,sans-serif', fontSize:10, letterSpacing:'0.14em',
                  textTransform:'uppercase', flex:1,
                  color:EU.catTint(catHue, 'text'),
                }}>{cat}</span>
                <span style={{
                  fontFamily:'DM Sans,sans-serif', fontSize:10,
                  color: complete ? EU.catTint(catHue, 'text') : C.textMuted,
                }}>{doneCnt}/{total}</span>
              </div>
              {/* 3px progress bar */}
              <div style={{height:3,background:'var(--b)',
                borderRadius:2,overflow:'hidden',marginBottom:10}}>
                <div style={{
                  height:'100%', borderRadius:2,
                  background:EU.catTint(catHue, 'text'),
                  width:`${pct*100}%`,
                  boxShadow: pct > 0 ? `0 0 5px ${EU.catTint(catHue, 'text')}` : 'none',
                  transition:'width 0.5s ease',
                }}/>
              </div>
              {/* 2-col grid of ActivityButtons */}
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6}}>
                {catActs.map(act => (
                  <ActivityButton key={act.key} act={act} catHue={catHue} onLog={logActivity}/>
                ))}
              </div>
            </div>
          );
        })}
        {acts.length === 0 && (
          <EmptyState
            icon="check-square"
            title="El día está en blanco"
            desc="Marcá tu primera virtud para abrir la cuenta de hoy."
            cta="Empezar"
            kbd="↓"
            onAction={() => {
              const first = document.querySelector('[data-cat]');
              if (first) {
                const top = first.getBoundingClientRect().top + window.scrollY - 80;
                window.scrollTo({ top, behavior: 'smooth' });
              }
            }}
          />
        )}
      </div>
      <UndoToast
        toast={undoToast.toast}
        onUndo={handleUndo}
        onDismiss={undoToast.dismiss}
        isDesktop={isDesktop}
      />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// PROFILE SCREEN
// ═══════════════════════════════════════════════════════════
function ProfileScreen({ appState, isDesktop }) {
  const { level, xp, xpNext, totalXP, modules } = appState;
  const d = window.__EUDAIMONIA_DATA__ || {};
  const maxStreak   = d.max_streak   ?? 0;
  const weeksActive = d.weeks_active ?? 0;
  const ecBalance   = (window.EU._server || {}).ecBalance ?? 0;
  const lv = EU.levels[level - 1];
  const xpPct = xpNext ? xp / xpNext : 1;

  return (
    <div style={{minHeight:'100vh', paddingBottom: isDesktop ? 48 : 100}}>
      <div style={{padding: isDesktop ? '28px 24px 0' : '16px 20px 0'}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.2em',
          color:C.gold,textTransform:'uppercase',opacity:0.6,marginBottom:4}}>ΑΥΤΟΣ</div>
        <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:28,
          fontWeight:600,color:C.text,letterSpacing:'0.05em',marginBottom:14}}>Perfil</div>

        {/* Perfil submodule link */}
        <a href="/perfil" style={{
          display:'flex',justifyContent:'space-between',alignItems:'center',
          background:C.card,border:'1px solid var(--gold-border)',
          borderRadius:12,padding:'13px 16px',marginBottom:20,
          textDecoration:'none',
        }}>
          <div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:15,
              fontWeight:600,color:C.text,letterSpacing:'0.08em'}}>Ver Perfil Completo</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              color:C.gold,letterSpacing:'0.1em',textTransform:'uppercase',marginTop:3,opacity:0.75}}>
              Medidas · Datos personales
            </div>
          </div>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:22,color:C.gold,opacity:0.5}}>→</div>
        </a>
      </div>

      {/* Level showcase */}
      <div style={{padding:'0 16px 20px'}}>
        <div style={{
          background:`linear-gradient(135deg,${C.card},${C.surface})`,
          border:'1px solid color-mix(in srgb, var(--gold) 20%, transparent)',borderRadius:20,
          padding:'24px',textAlign:'center',
          boxShadow:'0 8px 40px rgba(0,0,0,0.5)',
        }}>
          <div style={{display:'flex',justifyContent:'center',marginBottom:10}}>
            <GreekColumn level={level} xpPct={xpPct} size={80}/>
          </div>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.18em',
            color:C.gold,opacity:0.6}}>NIVEL {level}</div>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:30,
            fontWeight:600,color:C.text,letterSpacing:'0.08em',marginTop:3}}>{lv?.name}</div>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
            fontSize:14,color:C.textSub,marginTop:2}}>{lv?.sub}</div>
        </div>
      </div>

      {/* Stats */}
      <div style={{padding: isDesktop ? '0 24px' : '0 16px', display:'grid', gridTemplateColumns: isDesktop ? 'repeat(5,1fr)' : '1fr 1fr', gap:8, marginBottom:20}}>
        {[
          {label:'XP Total',      val: totalXP.toLocaleString()},
          {label:'Racha Mayor',   val:`${maxStreak} días`},
          {label:'Hoy',           val:`${modules.filter(m=>m.done).length}/${modules.length} mods`},
          {label:'Semanas activo',val:String(weeksActive)},
          {label:'EC Disponibles',val:`${ecBalance} 🪙`, accent: true, href:'/recompensas'},
        ].map(s => (
          <div key={s.label} onClick={s.href ? ()=>window.location.href=s.href : undefined} style={{
            background: s.accent ? 'color-mix(in srgb, var(--gold) 6%, transparent)' : C.card,
            border: s.accent ? '1px solid color-mix(in srgb, var(--gold) 25%, transparent)' : '1px solid var(--gold-bg)',
            borderRadius:12, padding:'14px',
            cursor: s.href ? 'pointer' : 'default',
          }}>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted,
              letterSpacing:'0.1em',textTransform:'uppercase',marginBottom:4}}>{s.label}</div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:24,color:C.gold}}>{s.val}</div>
          </div>
        ))}
      </div>

      {/* Level path */}
      <div style={{padding: isDesktop ? '0 24px' : '0 16px'}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',marginBottom:12}}>Camino al Eudaimón</div>
        {EU.levels.map(lv => (
          <div key={lv.n} style={{display:'flex',alignItems:'center',gap:12,
            padding:'9px 0',borderBottom:'1px solid color-mix(in srgb, var(--gold) 5%, transparent)',
            opacity: lv.n > level ? 0.35 : 1,transition:'opacity 0.3s'}}>
            <div style={{
              width:28,height:28,borderRadius:8,flexShrink:0,
              background: lv.n < level ? C.gold : lv.n===level ? 'var(--b)' : C.card,
              border:`1.5px solid ${lv.n<=level?C.gold:'var(--gold-bg)'}`,
              display:'flex',alignItems:'center',justifyContent:'center',
              fontFamily:'DM Sans,sans-serif',fontSize:10,
              color: lv.n < level ? C.deep : C.gold,
            }}>
              {lv.n < level ? '✓' : lv.n}
            </div>
            <div style={{flex:1}}>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:15,
                letterSpacing:'0.05em',color:lv.n<=level?C.text:C.textMuted}}>{lv.name}</div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>{lv.sub}</div>
            </div>
            {lv.n === level && (
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
                color:C.gold,opacity:0.7,letterSpacing:'0.08em'}}>ACTUAL</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, {
  HomeScreen, CommandCenterScreen, ModuleDetailScreen, ActaDiurnaScreen, PraxisInbox, ProfileScreen,
});
