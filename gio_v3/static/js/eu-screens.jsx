// EUDAIMONIA — All Screens
const { useState, useMemo, useEffect, useRef } = React;
const C = window.EU.getColors();

function todayQuote() {
  return EU.quotes[new Date().getDay() % EU.quotes.length];
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
            color:C.textMuted,fontSize:16,padding:0,lineHeight:1,
            display:'inline-flex',alignItems:'center',
            transform:spinning?'rotate(180deg)':'rotate(0deg)',
            transition:'transform 0.4s ease',
          }}>↻</button>
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
      background:'rgba(201,168,76,0.04)',
      border:'1px solid rgba(201,168,76,0.1)',
      borderRadius:12, padding:'16px 18px', marginBottom:14,
    }}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase'}}>Word of the Day</div>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span style={{fontFamily:'DM Sans,sans-serif',fontSize:8,color:'#60a5fa',
            background:'rgba(96,165,250,0.08)',border:'1px solid rgba(96,165,250,0.18)',
            padding:'2px 8px',borderRadius:100,letterSpacing:'0.06em'}}>EN → FR</span>
          <button onClick={refresh} style={{
            background:'transparent',border:'none',cursor:'pointer',
            color:C.textMuted,fontSize:16,padding:0,lineHeight:1,
            display:'inline-flex',alignItems:'center',
            transform:spinning?'rotate(180deg)':'rotate(0deg)',
            transition:'transform 0.4s ease',
          }}>↻</button>
        </div>
      </div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted,marginBottom:2,letterSpacing:'0.04em'}}>
        {word.phonetic}
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
        fontSize:28,fontWeight:300,color:C.text,lineHeight:1,marginBottom:10}}>
        {word.word}
      </div>
      <div style={{height:1,background:'linear-gradient(90deg,rgba(201,168,76,0.4),transparent)',marginBottom:10}}/>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textMuted,lineHeight:1.55,marginBottom:8}}>
        {word.meaning}
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',fontSize:12,
        color:C.textMuted,borderLeft:'2px solid rgba(201,168,76,0.3)',
        paddingLeft:10,marginBottom:10,lineHeight:1.55,opacity:0.75}}>
        "{word.example}"
      </div>
      <span style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
        background:'rgba(201,168,76,0.06)',border:'1px solid rgba(201,168,76,0.16)',
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
        background:'rgba(201,168,76,0.03)',
        border:'1px solid rgba(201,168,76,0.08)',
        borderRadius:12, overflow:'hidden',
      }}>
        {items.map((r, i) => {
          const dateStr = r.next_date || r.target_date || '';
          const isPeriodic = r.type === 'periodico';
          return (
            <div key={r.id} style={{
              display:'flex', alignItems:'center', gap:12,
              padding:'12px 16px',
              borderBottom: i < items.length - 1 ? '1px solid rgba(201,168,76,0.06)' : 'none',
              opacity: r._loading ? 0.4 : 1, transition:'opacity 0.2s',
            }}>
              <button onClick={() => !r._loading && handleDone(r.id, r.type)} style={{
                flexShrink:0, background:'none', border:'1.5px solid rgba(201,168,76,0.25)',
                width:18, height:18, borderRadius:'50%', cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center',
                transition:'border-color 0.15s, background 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor='rgba(201,168,76,0.7)'; e.currentTarget.style.background='rgba(201,168,76,0.1)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor='rgba(201,168,76,0.25)'; e.currentTarget.style.background='none'; }}
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
function DeadlineRadar() {
  const initial = (window.EU._server || {}).deadlines || [];
  const [deadlines, setDeadlines] = useState(initial);
  const [checking, setChecking] = useState({});

  if (!deadlines.length) return null;

  async function handleCheck(dl) {
    if (checking[dl.id]) return;
    setChecking(prev => ({...prev, [dl.id]: true}));
    try {
      const res = await fetch(`/perfil/api/reminder/${dl.id}/done`, {method:'POST'});
      const j = await res.json();
      if (j.ok) {
        setDeadlines(prev => prev.filter(d => d.id !== dl.id));
      }
    } catch(e) {}
    setChecking(prev => ({...prev, [dl.id]: false}));
  }

  const PAL = {
    red:    { text:'#f87171', bg:'rgba(239,68,68,0.09)',  border:'#ef4444', pill:'rgba(239,68,68,0.20)'  },
    amber:  { text:'#fbbf24', bg:'rgba(245,158,11,0.09)', border:'#f59e0b', pill:'rgba(245,158,11,0.20)' },
    yellow: { text:'#fde047', bg:'rgba(234,179,8,0.07)',  border:'#eab308', pill:'rgba(234,179,8,0.18)'  },
    green:  { text:'#34d399', bg:'rgba(16,185,129,0.07)', border:'#10b981', pill:'rgba(16,185,129,0.18)' },
  };
  const TYPE_ICON  = { reminder:'🔔', task:'☑️', wishlist:'🛍️' };
  const TYPE_LABEL = { reminder:'recordatorio', task:'tarea gtd', wishlist:'wishlist' };

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

      {/* Scroll horizontal */}
      <div style={{display:'flex',gap:10,overflowX:'auto',
        paddingBottom:6,scrollbarWidth:'none',WebkitOverflowScrolling:'touch'}}>
        {deadlines.map((dl, i) => {
          const p = PAL[dl.level] || PAL.green;
          const urgent = dl.level === 'red';
          const sublabel = dl.days > 0 ? 'DÍAS' : dl.days === 0 ? 'DEADLINE' : 'EXPIRADO';

          const isChecking = checking[dl.id];
          return (
            <div key={dl.id ?? i} style={{
              flexShrink:0,display:'flex',alignItems:'stretch',
              borderRadius:14,overflow:'hidden',
              border:'1px solid rgba(255,255,255,0.05)',
              background:p.bg,minWidth:185,maxWidth:215,
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
                  <div style={{display:'flex',alignItems:'center',gap:5}}>
                    <span style={{fontSize:10,lineHeight:1}}>{TYPE_ICON[dl.type] || '📌'}</span>
                    <span style={{fontFamily:'DM Sans,sans-serif',fontSize:8,
                      letterSpacing:'0.12em',textTransform:'uppercase',
                      color:p.text,opacity:0.65}}>{TYPE_LABEL[dl.type] || dl.type}</span>
                  </div>
                  <button
                    onClick={() => handleCheck(dl)}
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
                    <span style={{color:p.border,fontSize:11,lineHeight:1,fontWeight:700}}>✓</span>
                  </button>
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
        })}
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
  { rank:'carbon',  icon:'🪨', label:'Carbón',   color:'#475569', threshold:0  },
  { rank:'iron',    icon:'⚔️',  label:'Hierro',   color:'#94a3b8', threshold:8  },
  { rank:'gold',    icon:'🥇', label:'Oro',      color:'#fbbf24', threshold:16 },
  { rank:'diamond', icon:'💎', label:'Diamante', color:'#7dd3fc', threshold:20 },
];

function HomeScreen({ appState, dispatch, isDesktop }) {
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
      if (data.stats) {
        window.EU._server.xpToday = data.stats.xp_today ?? data.stats.pts_today ?? xpToday;
        window.EU._server.streak  = data.stats.streak ?? streak;
      }
    })
    .catch(() => {});
  };

  return (
    <div style={{paddingBottom: isDesktop ? 48 : 100, minHeight:'100vh'}}>
      {/* Sticky header */}
      <div style={{
        position:'sticky',top:0,zIndex:50,
        padding:'env(safe-area-inset-top,16px) 20px 12px',
        paddingTop:'max(env(safe-area-inset-top,16px),16px)',
        background:EU.rgba('deep', 0.97),
        borderBottom:'1px solid rgba(201,168,76,0.07)',
      }}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
          <div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              letterSpacing:'0.22em',color:C.gold,opacity:0.65,textTransform:'uppercase'}}>
              {fmtDate()}
            </div>
            <div style={{fontFamily:'Cormorant Garamond,serif',
              fontSize: isDesktop ? 24 : 20,
              color:C.text,fontWeight:500,
              letterSpacing: isDesktop ? '0.12em' : '0.18em',
              marginTop:1, whiteSpace:'nowrap'}}>
              {isDesktop ? 'Ε Υ Δ Α Ι Μ Ο Ν Ι Α' : 'ΕΥΔΑΙΜΟΝΙΑ'}
            </div>
          </div>
          <div style={{display:'flex',alignItems:'center',gap:10,paddingTop:4}}>
            {isDesktop && (
              <button onClick={() => window.dispatchEvent(new CustomEvent('eu:open-cmdk'))}
                style={{background:'rgba(201,168,76,0.08)',border:'1px solid rgba(201,168,76,0.2)',
                  borderRadius:6,padding:'3px 8px',color:C.gold,fontSize:10,cursor:'pointer',
                  fontFamily:'DM Sans,sans-serif',letterSpacing:'0.05em'}}>
                ⌘ K
              </button>
            )}
            <a href="/logros" style={{
              display:'inline-flex',alignItems:'center',gap:4,
              fontFamily:'DM Sans,sans-serif',fontSize:9,
              color:C.gold,opacity:0.65,textDecoration:'none',
              letterSpacing:'0.08em',
            }}>🏆 Logros</a>
          </div>
        </div>
      </div>

      <div style={{padding:'0 16px'}}>
        {/* ── SALUDO ── */}
        <div style={{padding:'20px 0 12px'}}>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:22,color:C.text}}>
            Buenos días, Gio.
          </div>
          <div style={{fontSize:11,color:C.textMuted,marginTop:2}}>
            {fmtDate()} · día {streak} de tu racha
          </div>
        </div>

        {/* ── HERO XP DEL DÍA ── */}
        <div style={{
          background:'linear-gradient(140deg,#1C1830,#110F20)',
          border:'1px solid rgba(201,168,76,0.18)',
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
          <div style={{height:5,background:'rgba(201,168,76,0.08)',borderRadius:3,overflow:'hidden',marginBottom:12}}>
            <div style={{
              height:'100%',borderRadius:3,
              background:'linear-gradient(90deg,#7A5520,#C9A84C,#E8C96D)',
              width:`${xpDayPct*100}%`,
              boxShadow:'0 0 8px rgba(201,168,76,0.45)',
              transition:'width 0.8s ease',
            }}/>
          </div>
          {/* ── Tier ladder ── */}
          {(() => {
            const clfData = clf;
            const curIdx  = TIERS.findIndex(t => t.rank === clfData.rank);
            const ci      = curIdx >= 0 ? curIdx : 0;
            const nt      = TIERS[ci + 1] || null;
            const col     = TIERS[ci].color;
            return (
              <>
                <div style={{display:'flex',alignItems:'flex-start',marginBottom:8}}>
                  {TIERS.map((t, i) => {
                    const active = i === ci;
                    const past   = i < ci;
                    return (
                      <React.Fragment key={t.rank}>
                        <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:4,flex:1}}>
                          <div style={{
                            width:active?9:5, height:active?9:5, borderRadius:'50%',
                            background:active ? col : past ? `${col}55` : 'rgba(255,255,255,0.08)',
                            boxShadow:active ? `0 0 9px ${col}` : 'none',
                            transition:'all 0.3s',
                          }}/>
                          <div style={{
                            fontFamily:'DM Sans,sans-serif', fontSize:7,
                            color:active ? col : C.textMuted,
                            opacity:active ? 1 : past ? 0.55 : 0.28,
                            textAlign:'center', lineHeight:1.3,
                          }}>{t.icon}<br/>{t.label}</div>
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
                    {nt ? `${nt.threshold - xpToday} XP → ${nt.label}` : '✦ Diamante alcanzado'}
                  </span>
                  <span style={{color:C.gold,opacity:0.7}}>
                    {xpNext ? `${xpNext - xp} XP → ${EU.levels[level]?.name || ''}` : ''}
                  </span>
                </div>
              </>
            );
          })()}
        </div>

        {/* ── SUGERENCIA DEL DÍA ── */}
        {suggestion && (
          <div onClick={() => logActivityFromHome(suggestion.key)}
            style={{
              background:`oklch(18% 0.04 ${(EU.catHues||{})[suggestion.cat]||45})`,
              border:`1px solid oklch(35% 0.09 ${(EU.catHues||{})[suggestion.cat]||45})`,
              borderRadius:12,padding:'14px 16px',marginBottom:14,cursor:'pointer',
              display:'flex',alignItems:'center',gap:12,
            }}>
            <div style={{flex:1}}>
              <div style={{fontSize:9,letterSpacing:'0.16em',textTransform:'uppercase',
                color:`oklch(65% 0.15 ${(EU.catHues||{})[suggestion.cat]||45})`,marginBottom:4}}>
                Un click cierra {suggestion.cat}
              </div>
              <div style={{fontSize:14,color:C.text}}>{suggestion.label}</div>
            </div>
            <span style={{fontSize:13,color:C.gold,fontWeight:600}}>+{suggestion.pts} XP</span>
          </div>
        )}

        {/* ── LEVEL CARD (compacto) ── */}
        <div style={{
          background:`linear-gradient(140deg,${C.card} 0%,${C.surface} 55%,${C.deep} 100%)`,
          border:'1px solid rgba(201,168,76,0.2)',
          borderRadius:16,padding:'18px 16px',marginBottom:14,
          position:'relative',overflow:'hidden',
          boxShadow:'0 8px 36px rgba(0,0,0,0.45), inset 0 1px 0 rgba(201,168,76,0.07)',
        }}>
          <div style={{position:'absolute',inset:0,pointerEvents:'none',background:
            'radial-gradient(ellipse at 15% 85%,rgba(201,168,76,0.05) 0%,transparent 55%),' +
            'radial-gradient(ellipse at 85% 15%,rgba(201,168,76,0.03) 0%,transparent 45%)'}}/>
          <div style={{display:'flex',alignItems:'flex-end',gap:14}}>
            <div style={{flexShrink:0}}>
              <GreekColumn level={level} xpPct={xpPct} size={72}/>
            </div>
            <div style={{flex:1,paddingBottom:3}}>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
                letterSpacing:'0.18em',color:C.gold,opacity:0.6,textTransform:'uppercase',marginBottom:2}}>
                NIVEL {level}
              </div>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:28,
                fontWeight:600,color:C.text,lineHeight:1,letterSpacing:'0.05em'}}>
                {lv?.name}
              </div>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
                fontSize:12,color:C.textSub,marginTop:3,marginBottom:10}}>
                {lv?.sub}
              </div>
              <div style={{height:3,background:'rgba(201,168,76,0.08)',borderRadius:2,overflow:'hidden'}}>
                <div style={{
                  height:'100%',borderRadius:2,
                  background:'linear-gradient(90deg,#7A5520,#C9A84C,#E8C96D)',
                  width:`${xpPct*100}%`,
                  boxShadow:'0 0 8px rgba(201,168,76,0.45)',
                  transition:'width 1.2s ease',
                }}/>
              </div>
            </div>
          </div>
        </div>

        {/* ── MÓDULOS HOY ── */}
        <div style={{marginBottom:14}}>
          <div style={{display:'flex',justifyContent:'space-between',
            alignItems:'baseline',marginBottom:6}}>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              letterSpacing:'0.15em',color:C.textMuted,textTransform:'uppercase'}}>
              Módulos
            </div>
            <div style={{fontSize:11,color:C.textMuted}}>
              {modules.filter(m => m.done).length} de {modules.length}
            </div>
          </div>
          {/* Daily progress mini-strip */}
          <div style={{
            display:'flex',gap:3,marginBottom:10,
            height:3,borderRadius:2,overflow:'hidden',
            background:'rgba(201,168,76,0.06)',
          }}>
            {modules.map(mod => (
              <div key={mod.id} style={{
                flex:1,height:'100%',
                background: mod.done ? `oklch(65% 0.15 ${mod.hue})` : 'transparent',
                transition:'background 0.4s',
              }}/>
            ))}
          </div>
          <div style={{display:'flex',gap:8,overflowX:'auto',paddingBottom:4,scrollbarWidth:'none'}}>
            {modules.map(mod => {
              const acc = `oklch(65% 0.15 ${mod.hue})`;
              const accBg = `oklch(18% 0.04 ${mod.hue})`;
              return (
                <div key={mod.id} onClick={() => dispatch({type:'OPEN_MODULE',id:mod.id})}
                  style={{flexShrink:0,display:'flex',flexDirection:'column',alignItems:'center',gap:5,cursor:'pointer'}}>
                  <div style={{
                    width:44,height:44,borderRadius:13,
                    background: mod.done ? accBg : C.card,
                    border:`1.5px solid ${mod.done ? acc : C.goldBorder}`,
                    display:'flex',alignItems:'center',justifyContent:'center',
                    boxShadow: mod.done ? `0 0 14px ${accBg}` : 'none',
                    transition:'all 0.3s',
                  }}>
                    <div style={{width:7,height:7,borderRadius:'50%',
                      background: mod.done ? acc : C.textMuted,
                      boxShadow: mod.done ? `0 0 6px ${acc}` : 'none'}}/>
                  </div>
                  <div style={{fontFamily:'DM Sans,sans-serif',fontSize:7,
                    color:mod.done?acc:C.textMuted,textAlign:'center',
                    letterSpacing:'0.04em',maxWidth:46,lineHeight:1.2}}>
                    {mod.name.slice(0,7)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── HEATMAP RACHA ── */}
        <div style={{
          background:C.card, border:`1px solid ${C.goldBorder}`,
          borderRadius:12, padding:'14px 16px', marginBottom:14,
        }}>
          <div style={{display:'flex',justifyContent:'space-between',
            alignItems:'baseline',marginBottom:10}}>
            <div style={{fontSize:10,letterSpacing:'0.18em',color:C.gold,
              opacity:0.7,textTransform:'uppercase'}}>Racha · {streak} días</div>
            <a href="/logros" style={{fontSize:10,color:C.gold,opacity:0.6,
              textDecoration:'none'}}>Ver historial →</a>
          </div>
          <StreakHeatmap days={21} compact={true}/>
        </div>

        {/* ── REFLEXION ── */}
        <ReflexionDelDia/>

        {/* ── WORD OF THE DAY ── */}
        <WordOfDay/>

        {/* ── DEADLINE RADAR ── */}
        <DeadlineRadar/>
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
          height:3,borderRadius:2,overflow:'hidden',background:'rgba(201,168,76,0.06)',
        }}>
          {modules.map(mod => (
            <div key={mod.id} style={{
              flex:1,height:'100%',
              background: mod.done ? `oklch(65% 0.15 ${mod.hue})` : 'transparent',
              transition:'background 0.4s',
            }}/>
          ))}
        </div>
      </div>

      <div style={{padding: isDesktop ? '0 24px' : '0 16px', display:'grid', gridTemplateColumns:cols, gap:10}}>
        {modules.map(mod => (
          <ModuleCard key={mod.id} mod={mod}
            onClick={() => dispatch({type:'OPEN_MODULE',id:mod.id})}/>
        ))}
        {/* PRAXIS + LOGROS — bottom full-width cards */}
        <a href="/gtd"
          style={{
            gridColumn:'1/-1',
            background:C.card,border:'1px solid rgba(201,168,76,0.14)',
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
            background:'rgba(201,168,76,0.04)',
            border:'1px solid rgba(201,168,76,0.14)',
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
  const acc    = `oklch(65% 0.15 ${mod.hue})`;
  const accDeep = `oklch(14% 0.04 ${mod.hue})`;
  const accMid  = `oklch(28% 0.07 ${mod.hue})`;

  return (
    <div style={{minHeight:'100vh', paddingBottom: isDesktop ? 48 : 100}}>
      {/* Hero header */}
      <div style={{
        padding: isDesktop ? '28px 24px 28px' : '16px 20px 24px',
        background:`linear-gradient(170deg,${accDeep} 0%,transparent 100%)`,
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
        {/* Submodules */}
        {(() => {
          const subs = (EU.submodules && EU.submodules[mod.id]) || [];
          return (
            <div style={{marginBottom:24}}>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
                color:C.textMuted,textTransform:'uppercase',marginBottom:12}}>Submódulos</div>
              {subs.length > 0 ? (
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
                  {subs.map((sub,i) => (
                    <a key={i} href={sub.route} style={{
                      display:'flex',alignItems:'center',gap:10,
                      background:accDeep, border:`1px solid ${accMid}`,
                      borderRadius:12, padding:'14px',
                      textDecoration:'none', transition:'all 0.2s',
                    }}>
                      <span style={{fontSize:20,lineHeight:1}}>{sub.icon}</span>
                      <span style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:acc,flex:1}}>{sub.name}</span>
                      <span style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:acc,opacity:0.6}}>→</span>
                    </a>
                  ))}
                </div>
              ) : (
                <div style={{background:accDeep,border:'1px dashed rgba(201,168,76,0.15)',
                  borderRadius:12,padding:'18px',textAlign:'center'}}>
                  <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.18em',
                    color:C.textMuted,textTransform:'uppercase',opacity:0.6}}>Próximamente</div>
                </div>
              )}
            </div>
          );
        })()}

        {/* Module-specific content */}
        <ModuleExtra id={mod.id} acc={acc}/>
      </div>
    </div>
  );
}

function ModuleExtra({ id, acc }) {
  const srv = (window.EU._server) || {};

  if (id === 'oikonomia') {
    const fin = srv.financial || {};
    const gastos  = fin.gastos  ? `$${Number(fin.gastos).toLocaleString('es-MX', {maximumFractionDigits:0})}` : '—';
    const ingreso = fin.ingreso ? `$${Number(fin.ingreso).toLocaleString('es-MX', {maximumFractionDigits:0})}` : '—';
    const deudas  = fin.deudas  ? `$${Number(fin.deudas).toLocaleString('es-MX', {maximumFractionDigits:0})}` : '—';
    const ahorro  = (fin.ingreso && fin.gastos) ? `$${(fin.ingreso - fin.gastos).toLocaleString('es-MX', {maximumFractionDigits:0})}` : '—';
    return (
      <div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',marginBottom:12}}>Resumen Financiero</div>
        {[
          {label:'Gastos del mes',   val: gastos,  sub: `de ${ingreso} ingreso`},
          {label:'Ahorro neto',      val: ahorro,  sub:'ingreso − gastos'},
          {label:'Deudas activas',   val: deudas,  sub:'saldo actual total'},
        ].map((r,i) => (
          <div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',
            padding:'12px 0',borderBottom:'1px solid rgba(201,168,76,0.06)'}}>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textSub}}>{r.label}</div>
            <div style={{textAlign:'right'}}>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:20,color:acc}}>{r.val}</div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>{r.sub}</div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (id === 'cosmopolitismo') {
    const langs = (srv.langStats && srv.langStats.length)
      ? srv.langStats
      : [{lang:'Alemán',lvl:'B1+',entries:0,pct:0.72},{lang:'Inglés',lvl:'C1',entries:0,pct:0.91},{lang:'Francés',lvl:'A2',entries:0,pct:0.25}];
    return (
      <div>
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
            <div style={{height:3,background:'rgba(201,168,76,0.08)',borderRadius:2}}>
              <div style={{height:'100%',borderRadius:2,background:acc,
                width:`${(l.pct||0)*100}%`,boxShadow:`0 0 6px ${acc}66`}}/>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (id === 'hegemonikon') {
    const b = srv.body || {};
    const rows = [
      {label:'Peso',      val: b.peso     || '—', sub: b.estatura ? `Estatura: ${b.estatura}` : ''},
      {label:'Pecho',     val: b.pecho    || '—', sub: b.cintura ? `Cintura: ${b.cintura}` : ''},
      {label:'Hombros',   val: b.hombros  || '—', sub: b.manga   ? `Manga: ${b.manga}`    : ''},
      {label:'T. Camisa', val: b.t_camisa || '—', sub: b.t_pantalon ? `Pantalón: ${b.t_pantalon}` : ''},
    ];
    return (
      <div>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',marginBottom:14}}>Métricas Corporales</div>
        {rows.map((r,i) => (
          <div key={i} style={{display:'flex',justifyContent:'space-between',
            padding:'11px 0',borderBottom:'1px solid rgba(201,168,76,0.06)'}}>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textSub}}>{r.label}</div>
            <div style={{textAlign:'right'}}>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:19,color:acc}}>{r.val}</div>
              {r.sub && <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>{r.sub}</div>}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (id === 'paideia') return (
    <div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Lectura Activa</div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textMuted,
        padding:'12px 0',fontStyle:'italic'}}>
        Registra tus libros en la sección de actividades.
      </div>
    </div>
  );

  return null;
}

// ═══════════════════════════════════════════════════════════
// PRAXIS INBOX — GTD tabs (extracted, not yet wired to Acta)
// ═══════════════════════════════════════════════════════════
function PraxisInbox({ isDesktop }) {
  const [gtdTab, setGtdTab] = useState('inbox');
  const [inbox, setInbox]   = useState(EU.gtd.inbox);
  const [newItem, setNewItem] = useState('');

  const addItem = () => {
    if (!newItem.trim()) return;
    setInbox(p => [...p, {id:Date.now(), text:newItem.trim(), context:'@inbox'}]);
    setNewItem('');
  };

  const GTD_TABS = [
    {id:'inbox',    label:'Inbox'},
    {id:'projects', label:'Proyectos'},
    {id:'contexts', label:'Contextos'},
    {id:'review',   label:'Revisión'},
  ];

  return (
    <div style={{borderTop:'1px solid rgba(201,168,76,0.1)', marginTop:4}}>
      <div style={{
        display:'flex', borderBottom:'1px solid rgba(201,168,76,0.1)',
        padding: isDesktop ? '0 24px' : '0 20px',
      }}>
        {GTD_TABS.map(t => (
          <div key={t.id} onClick={() => setGtdTab(t.id)} style={{
            flex:1, padding:'11px 2px', textAlign:'center', cursor:'pointer',
            fontFamily:'DM Sans,sans-serif', fontSize:11,
            color: gtdTab===t.id ? C.gold : C.textMuted,
            borderBottom: gtdTab===t.id ? `2px solid ${C.gold}` : '2px solid transparent',
            transition:'all 0.2s',
          }}>{t.label}</div>
        ))}
      </div>

      <div style={{padding: isDesktop ? '16px 24px 0' : '16px 20px 0'}}>
        {gtdTab === 'inbox' && (
          <div>
            <div style={{display:'flex',gap:8,marginBottom:14,
              background:C.card,border:'1px solid rgba(201,168,76,0.14)',
              borderRadius:10,padding:'4px 4px 4px 14px',alignItems:'center'}}>
              <input value={newItem} onChange={e=>setNewItem(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&addItem()}
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
                  padding:'11px 0',borderBottom:'1px solid rgba(201,168,76,0.06)'}}>
                  <div style={{width:5,height:5,borderRadius:'50%',
                    background:'rgba(201,168,76,0.28)',flexShrink:0}}/>
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
            <div key={p.id} style={{background:C.card,border:'1px solid rgba(201,168,76,0.1)',
              borderRadius:12,padding:'14px 16px',marginBottom:9}}>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text,marginBottom:9}}>{p.name}</div>
              <div style={{display:'flex',alignItems:'center',gap:10}}>
                <div style={{flex:1,height:3,background:'rgba(201,168,76,0.08)',borderRadius:2}}>
                  <div style={{height:'100%',borderRadius:2,background:C.gold,
                    width:`${pct*100}%`,boxShadow:'0 0 6px rgba(201,168,76,0.5)'}}/>
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
                background:C.card,border:'1px solid rgba(201,168,76,0.12)',
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
                padding:'10px 0',borderBottom:'1px solid rgba(201,168,76,0.06)'}}>
                <div style={{
                  width:20,height:20,borderRadius:6,flexShrink:0,
                  border:`1.5px solid ${item.done?C.gold:'rgba(201,168,76,0.2)'}`,
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
      border:'1px solid rgba(201,168,76,0.25)',
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
        border:'1px solid rgba(201,168,76,0.3)',
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
  const burstColor = isAlto ? '#fbbf24' : `oklch(65% 0.18 ${catHue})`;

  return (
    <div onClick={handle} style={{
      display:'flex', flexDirection:'column',
      padding:'10px 12px', borderRadius:10, cursor:'pointer',
      background: act.done
        ? (isAlto ? 'rgba(245,158,11,0.07)' : 'rgba(99,102,241,0.07)')
        : C.card,
      border: act.done
        ? (isAlto ? '1px solid rgba(245,158,11,0.3)' : '1px solid rgba(99,102,241,0.25)')
        : `1px solid oklch(22% 0.05 ${catHue})`,
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
            : `oklch(32% 0.08 ${catHue})`}`,
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
            : `oklch(18% 0.03 ${catHue})`,
          color: act.done ? '#fff' : `oklch(55% 0.12 ${catHue})`,
          border: act.done ? 'none' : `1px solid oklch(28% 0.06 ${catHue})`,
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
          background:'linear-gradient(140deg,#1C1830,#110F20)',
          border:'1px solid rgba(201,168,76,0.18)',
          borderRadius:16, padding:'20px', marginBottom:14,
          position:'relative', overflow:'hidden',
        }}>
          {/* Header row: label + clf chip */}
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:6}}>
            <div style={{fontSize:9,letterSpacing:'0.18em',color:C.gold,
              opacity:0.6,textTransform:'uppercase'}}>Acta Diurna · XP hoy</div>
            {clf.rank && (
              <div style={{display:'flex',alignItems:'center',gap:5,
                background:'rgba(255,255,255,0.05)',borderRadius:20,padding:'3px 10px'}}>
                <span style={{fontSize:12}}>{TIERS.find(t=>t.rank===clf.rank)?.icon||'🪨'}</span>
                <span style={{fontSize:9,color:C.textMuted,letterSpacing:'0.08em',
                  textTransform:'uppercase'}}>{TIERS.find(t=>t.rank===clf.rank)?.label||'Carbón'}</span>
              </div>
            )}
          </div>
          {/* XP numeral */}
          <div style={{display:'flex',alignItems:'baseline',gap:8,marginBottom:12}}>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:64,
              lineHeight:1,color:C.goldLight,fontWeight:600}}>{xpToday}</div>
            <div style={{fontSize:13,color:C.textMuted}}>/ {XP_GOAL} meta</div>
          </div>
          {/* Progress bar */}
          <div style={{height:5,background:'rgba(201,168,76,0.08)',borderRadius:3,overflow:'hidden',marginBottom:12}}>
            <div style={{
              height:'100%',borderRadius:3,
              background:'linear-gradient(90deg,#7A5520,#C9A84C,#E8C96D)',
              width:`${xpDayPct*100}%`,
              boxShadow:'0 0 8px rgba(201,168,76,0.45)',
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
                    return (
                      <React.Fragment key={t.rank}>
                        <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:4,flex:1}}>
                          <div style={{
                            width:active?9:5, height:active?9:5, borderRadius:'50%',
                            background:active ? col : past ? `${col}55` : 'rgba(255,255,255,0.08)',
                            boxShadow:active ? `0 0 9px ${col}` : 'none',
                            transition:'all 0.3s',
                          }}/>
                          <div style={{
                            fontFamily:'DM Sans,sans-serif', fontSize:7,
                            color:active ? col : C.textMuted,
                            opacity:active ? 1 : past ? 0.55 : 0.28,
                            textAlign:'center', lineHeight:1.3,
                          }}>{t.icon}<br/>{t.label}</div>
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
              background:C.card, border:'1px solid rgba(201,168,76,0.08)',
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
              background:`oklch(14% 0.03 ${catHue})`,
              border:`1px solid oklch(${complete ? '35% 0.10' : '22% 0.05'} ${catHue})`,
              borderRadius:14, padding:'14px', marginBottom:14,
              transition:'border-color 0.3s',
            }}>
              {/* Header: dot · name · X/Y */}
              <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
                <div style={{
                  width:7, height:7, borderRadius:'50%', flexShrink:0,
                  background: doneCnt > 0
                    ? `oklch(60% 0.18 ${catHue})`
                    : `oklch(28% 0.07 ${catHue})`,
                  boxShadow: doneCnt > 0 ? `0 0 6px oklch(60% 0.18 ${catHue})` : 'none',
                  transition:'all 0.3s',
                }}/>
                <span style={{
                  fontFamily:'DM Sans,sans-serif', fontSize:10, letterSpacing:'0.14em',
                  textTransform:'uppercase', flex:1,
                  color:`oklch(65% 0.14 ${catHue})`,
                }}>{cat}</span>
                <span style={{
                  fontFamily:'DM Sans,sans-serif', fontSize:10,
                  color: complete ? `oklch(65% 0.14 ${catHue})` : C.textMuted,
                }}>{doneCnt}/{total}</span>
              </div>
              {/* 3px progress bar */}
              <div style={{height:3,background:`oklch(20% 0.04 ${catHue})`,
                borderRadius:2,overflow:'hidden',marginBottom:10}}>
                <div style={{
                  height:'100%', borderRadius:2,
                  background:`oklch(55% 0.16 ${catHue})`,
                  width:`${pct*100}%`,
                  boxShadow: pct > 0 ? `0 0 5px oklch(55% 0.16 ${catHue})` : 'none',
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
          background:C.card,border:'1px solid rgba(201,168,76,0.16)',
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
          border:'1px solid rgba(201,168,76,0.2)',borderRadius:20,
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
            background: s.accent ? 'rgba(201,168,76,0.06)' : C.card,
            border: s.accent ? '1px solid rgba(201,168,76,0.25)' : '1px solid rgba(201,168,76,0.1)',
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
            padding:'9px 0',borderBottom:'1px solid rgba(201,168,76,0.05)',
            opacity: lv.n > level ? 0.35 : 1,transition:'opacity 0.3s'}}>
            <div style={{
              width:28,height:28,borderRadius:8,flexShrink:0,
              background: lv.n < level ? C.gold : lv.n===level ? 'rgba(201,168,76,0.15)' : C.card,
              border:`1.5px solid ${lv.n<=level?C.gold:'rgba(201,168,76,0.1)'}`,
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
