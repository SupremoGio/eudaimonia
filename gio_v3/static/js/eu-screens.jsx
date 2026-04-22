// EUDAIMONIA — All Screens
const { useState, useMemo } = React;
const C = window.EU.c;

function todayQuote() {
  return EU.quotes[new Date().getDay() % EU.quotes.length];
}
function fmtDate() {
  const d = new Date();
  const days = ['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];
  const mos  = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  return `${days[d.getDay()]} ${d.getDate()} de ${mos[d.getMonth()]}`;
}

// ═══════════════════════════════════════════════════════════
// HOME SCREEN
// ═══════════════════════════════════════════════════════════
function HomeScreen({ appState, dispatch, isDesktop }) {
  const { level, xp, xpNext, modules } = appState;
  const lv = EU.levels[level - 1];
  const xpPct = xpNext ? xp / xpNext : 1;
  const quote = useMemo(todayQuote, []);
  const doneCount = modules.filter(m => m.done).length;

  return (
    <div style={{paddingBottom: isDesktop ? 48 : 100, minHeight:'100vh'}}>
      {/* Sticky header */}
      <div style={{
        position:'sticky',top:0,zIndex:50,
        padding:'env(safe-area-inset-top,16px) 20px 12px',
        paddingTop:'max(env(safe-area-inset-top,16px),16px)',
        background:'rgba(9,7,15,0.97)',
        borderBottom:'1px solid rgba(201,168,76,0.07)',
      }}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
          <div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              letterSpacing:'0.22em',color:C.gold,opacity:0.65,textTransform:'uppercase'}}>
              {fmtDate()}
            </div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:24,
              color:C.text,fontWeight:500,letterSpacing:'0.12em',marginTop:1}}>
              Ε Υ Δ Α Ι Μ Ο Ν Ι Α
            </div>
          </div>
          <div style={{textAlign:'right',paddingTop:2}}>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.textMuted}}>
              {doneCount}/{modules.length} módulos
            </div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.gold,marginTop:2}}>
              {xp} / {xpNext} XP
            </div>
          </div>
        </div>
      </div>

      <div style={{padding:'0 16px'}}>
        {/* ── LEVEL CARD ── */}
        <div style={{
          background:'linear-gradient(140deg,#1C1830 0%,#110F20 55%,#0F0D1C 100%)',
          border:'1px solid rgba(201,168,76,0.2)',
          borderRadius:20,padding:'24px 18px 22px',marginBottom:14,
          position:'relative',overflow:'hidden',
          boxShadow:'0 10px 48px rgba(0,0,0,0.55), inset 0 1px 0 rgba(201,168,76,0.08)',
        }}>
          {/* Marble veins */}
          <div style={{position:'absolute',inset:0,pointerEvents:'none',background:
            'radial-gradient(ellipse at 15% 85%,rgba(201,168,76,0.05) 0%,transparent 55%),' +
            'radial-gradient(ellipse at 85% 15%,rgba(201,168,76,0.03) 0%,transparent 45%)'}}/>

          <div style={{display:'flex',alignItems:'flex-end',gap:18}}>
            <div style={{flexShrink:0}}>
              <GreekColumn level={level} xpPct={xpPct} size={96}/>
            </div>
            <div style={{flex:1,paddingBottom:4}}>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
                letterSpacing:'0.18em',color:C.gold,opacity:0.6,textTransform:'uppercase',marginBottom:3}}>
                NIVEL {level}
              </div>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:34,
                fontWeight:600,color:C.text,lineHeight:1,letterSpacing:'0.05em'}}>
                {lv?.name}
              </div>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
                fontSize:14,color:C.textSub,marginTop:4,marginBottom:14}}>
                {lv?.sub}
              </div>
              {/* XP Bar */}
              <div>
                <div style={{height:4,background:'rgba(201,168,76,0.08)',borderRadius:2,overflow:'hidden'}}>
                  <div style={{
                    height:'100%',borderRadius:2,
                    background:'linear-gradient(90deg,#7A5520,#C9A84C,#E8C96D)',
                    width:`${xpPct*100}%`,
                    boxShadow:'0 0 10px rgba(201,168,76,0.55)',
                    transition:'width 1.2s ease',
                  }}/>
                </div>
                <div style={{display:'flex',justifyContent:'space-between',marginTop:5}}>
                  <span style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>Experiencia</span>
                  <span style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.gold,opacity:0.7}}>
                    {xpNext ? `${xpNext - xp} XP para ${EU.levels[level]?.name}` : 'MÁXIMO NIVEL'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── MÓDULOS HOY ── */}
        <div style={{marginBottom:14}}>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
            color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Hoy</div>
          <div style={{display:'flex',gap:8,overflowX:'auto',paddingBottom:4,scrollbarWidth:'none'}}>
            {modules.map(mod => {
              const acc = `oklch(65% 0.15 ${mod.hue})`;
              const accBg = `oklch(18% 0.04 ${mod.hue})`;
              return (
                <div key={mod.id} onClick={() => dispatch({type:'OPEN_MODULE',id:mod.id})}
                  style={{flexShrink:0,display:'flex',flexDirection:'column',alignItems:'center',gap:5,cursor:'pointer'}}>
                  <div style={{
                    width:44,height:44,borderRadius:13,
                    background: mod.done ? accBg : 'rgba(201,168,76,0.04)',
                    border:`1.5px solid ${mod.done ? acc : 'rgba(201,168,76,0.1)'}`,
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

        {/* ── QUOTE ── */}
        <div style={{marginBottom:14}}>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
            color:C.textMuted,textTransform:'uppercase',marginBottom:10}}>Reflexión del Día</div>
          <QuoteDisplay quote={quote}/>
        </div>

        {/* ── NEXT ACTIONS ── */}
        <div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
              color:C.textMuted,textTransform:'uppercase'}}>Próximas Acciones</div>
            <div onClick={() => dispatch({type:'SET_TAB',tab:'gtd'})}
              style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.gold,cursor:'pointer',opacity:0.75}}>
              Ver todo →
            </div>
          </div>
          {EU.gtd.inbox.slice(0,3).map(item => (
            <div key={item.id} style={{
              display:'flex',alignItems:'center',gap:10,padding:'10px 0',
              borderBottom:'1px solid rgba(201,168,76,0.06)',
            }}>
              <div style={{width:5,height:5,borderRadius:'50%',
                background:'rgba(201,168,76,0.25)',flexShrink:0}}/>
              <div style={{flex:1,fontFamily:'DM Sans,sans-serif',fontSize:13,color:C.text}}>{item.text}</div>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>{item.context}</div>
            </div>
          ))}
        </div>
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
        {/* GTD card */}
        <div onClick={() => dispatch({type:'SET_TAB',tab:'gtd'})}
          style={{
            gridColumn:'1/-1',
            background:C.card,border:'1px solid rgba(201,168,76,0.14)',
            borderRadius:14,padding:'14px 15px',cursor:'pointer',
            display:'flex',justifyContent:'space-between',alignItems:'center',
            transition:'all 0.25s',
          }}>
          <div>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:15,
              fontWeight:600,color:C.text,letterSpacing:'0.08em'}}>PRAXIS</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
              color:C.gold,letterSpacing:'0.1em',textTransform:'uppercase',marginTop:3}}>
              Registro Diario · GTD
            </div>
          </div>
          <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:22,color:C.gold,opacity:0.5}}>→</div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// MODULE DETAIL
// ═══════════════════════════════════════════════════════════
function ModuleDetailScreen({ mod, appState, dispatch, isDesktop }) {
  const [habits, setHabits] = useState(EU.moduleHabits[mod.id] || []);
  const acc = `oklch(65% 0.15 ${mod.hue})`;
  const accDeep = `oklch(14% 0.04 ${mod.hue})`;
  const accMid = `oklch(28% 0.07 ${mod.hue})`;

  const toggle = (i) => {
    setHabits(prev => prev.map((h, idx) => {
      if (idx !== i) return h;
      if (!h.done) dispatch({ type:'ADD_XP', amount: h.xp });
      return {...h, done: !h.done};
    }));
  };
  const doneCnt = habits.filter(h => h.done).length;

  return (
    <div style={{minHeight:'100vh', paddingBottom: isDesktop ? 48 : 100}}>
      {/* Hero header */}
      <div style={{
        padding: isDesktop ? '28px 24px 28px' : '16px 20px 24px',
        background:`linear-gradient(170deg,${accDeep} 0%,rgba(9,7,15,0) 100%)`,
        borderBottom:`1px solid ${accMid}`,
      }}>
        <button onClick={() => dispatch({type:'CLOSE_MODULE'})}
          style={{background:'none',border:'none',color:C.textMuted,
            fontFamily:'DM Sans,sans-serif',fontSize:12,cursor:'pointer',
            padding:0,marginBottom:14,display:'flex',alignItems:'center',gap:6}}>
          ← Módulos
        </button>
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
        <div style={{display:'flex',gap:24,marginTop:16}}>
          {[
            {label:'Racha', val:`${mod.streak}d`},
            {label:'Hoy', val:`${doneCnt}/${habits.length}`},
            {label:'Estado', val: doneCnt===habits.length?'✓':'Pendiente'},
          ].map(s => (
            <div key={s.label}>
              <div style={{fontFamily:'DM Sans,sans-serif',fontSize:8,
                color:C.textMuted,letterSpacing:'0.1em',textTransform:'uppercase',marginBottom:2}}>{s.label}</div>
              <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:20,color:acc}}>{s.val}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{padding: isDesktop ? '24px 24px 0' : '20px 16px 0'}}>
        {/* Habits */}
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
          color:C.textMuted,textTransform:'uppercase',marginBottom:2}}>Práctica Diaria</div>
        {habits.map((h,i) => (
          <HabitRow key={i} label={h.label} done={h.done}
            onToggle={() => toggle(i)} xp={h.xp} accent={acc}/>
        ))}

        {/* Module-specific content */}
        <div style={{marginTop:24}}>
          <ModuleExtra id={mod.id} acc={acc}/>
        </div>
      </div>
    </div>
  );
}

function ModuleExtra({ id, acc }) {
  if (id === 'oikonomia') return (
    <div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:12}}>Resumen Financiero</div>
      {[
        {label:'Gastos del mes',   val:'$2,840', sub:'de $3,500 presupuesto'},
        {label:'Ahorro neto',      val:'$1,260', sub:'+12% vs mes anterior'},
        {label:'Deudas activas',   val:'$8,400', sub:'2 cuentas · pagando'},
        {label:'Inversiones',      val:'$14,200',sub:'+4.2% este trimestre'},
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

  if (id === 'cosmopolitismo') return (
    <div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:14}}>Idiomas en Progreso</div>
      {[
        {lang:'Alemán', lvl:'B1+', streak:33, pct:0.72},
        {lang:'Inglés', lvl:'C1',  streak:120,pct:0.91},
        {lang:'Francés',lvl:'A2',  streak:7,  pct:0.25},
      ].map((l,i) => (
        <div key={i} style={{marginBottom:16}}>
          <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
            <span style={{fontFamily:'Cormorant Garamond,serif',fontSize:17,color:C.text}}>{l.lang}</span>
            <span style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:acc}}>{l.lvl} · {l.streak}d ◆</span>
          </div>
          <div style={{height:3,background:'rgba(201,168,76,0.08)',borderRadius:2}}>
            <div style={{height:'100%',borderRadius:2,background:acc,
              width:`${l.pct*100}%`,boxShadow:`0 0 6px ${acc}66`}}/>
          </div>
        </div>
      ))}
    </div>
  );

  if (id === 'paideia') return (
    <div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:14}}>Lectura Activa</div>
      {[
        {title:'Meditaciones',      auth:'Marco Aurelio',  pct:0.62, pages:'148/240'},
        {title:'El Arte de la Guerra',auth:'Sun Tzu',     pct:0.95, pages:'190/200'},
        {title:'Antifragil',        auth:'N. N. Taleb',   pct:0.30, pages:'120/400'},
      ].map((b,i) => (
        <div key={i} style={{display:'flex',gap:12,padding:'10px 0',
          borderBottom:'1px solid rgba(201,168,76,0.06)'}}>
          <div style={{width:32,height:42,borderRadius:4,background:'rgba(201,168,76,0.08)',
            border:'1px solid rgba(201,168,76,0.15)',flexShrink:0}}/>
          <div style={{flex:1}}>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:15,color:C.text}}>{b.title}</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,color:C.textMuted,marginBottom:6}}>{b.auth}</div>
            <div style={{height:2,background:'rgba(201,168,76,0.08)',borderRadius:1}}>
              <div style={{height:'100%',borderRadius:1,background:acc,width:`${b.pct*100}%`}}/>
            </div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted,marginTop:3}}>{b.pages}</div>
          </div>
        </div>
      ))}
    </div>
  );

  if (id === 'hegemonikon') return (
    <div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.15em',
        color:C.textMuted,textTransform:'uppercase',marginBottom:14}}>Métricas Corporales</div>
      {[
        {label:'Peso actual',  val:'74.2 kg', sub:'objetivo: 72 kg'},
        {label:'Pasos hoy',    val:'6,240',   sub:'objetivo: 8,000'},
        {label:'Hidratación',  val:'1.8 L',   sub:'objetivo: 2.5 L'},
        {label:'Horas sueño',  val:'7h 20m',  sub:'objetivo: 8h'},
      ].map((r,i) => (
        <div key={i} style={{display:'flex',justifyContent:'space-between',
          padding:'11px 0',borderBottom:'1px solid rgba(201,168,76,0.06)'}}>
          <div style={{fontFamily:'DM Sans,sans-serif',fontSize:12,color:C.textSub}}>{r.label}</div>
          <div style={{textAlign:'right'}}>
            <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:19,color:acc}}>{r.val}</div>
            <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>{r.sub}</div>
          </div>
        </div>
      ))}
    </div>
  );

  return null;
}

// ═══════════════════════════════════════════════════════════
// GTD SCREEN
// ═══════════════════════════════════════════════════════════
function GTDScreen({ appState, dispatch, isDesktop }) {
  const [tab, setTab] = useState('inbox');
  const [inbox, setInbox] = useState(EU.gtd.inbox);
  const [newItem, setNewItem] = useState('');

  const addItem = () => {
    if (!newItem.trim()) return;
    setInbox(p => [...p, {id:Date.now(), text:newItem.trim(), context:'@inbox'}]);
    setNewItem('');
  };

  const TABS = [{id:'inbox',label:'Inbox'},{id:'projects',label:'Proyectos'},
                {id:'contexts',label:'Contextos'},{id:'review',label:'Revisión'}];

  return (
    <div style={{minHeight:'100vh', paddingBottom: isDesktop ? 48 : 100}}>
      <div style={{padding: isDesktop ? '28px 24px 0' : '16px 20px 0'}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.2em',
          color:C.gold,textTransform:'uppercase',opacity:0.6,marginBottom:4}}>MÉTODO GTD</div>
        <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:28,
          fontWeight:600,color:C.text,letterSpacing:'0.06em',marginBottom:16,fontStyle:'italic'}}>Acta Diurna</div>
        {/* Tab bar */}
        <div style={{display:'flex',borderBottom:'1px solid rgba(201,168,76,0.1)',marginBottom:-1}}>
          {TABS.map(t => (
            <div key={t.id} onClick={() => setTab(t.id)} style={{
              flex:1,padding:'8px 2px',textAlign:'center',cursor:'pointer',
              fontFamily:'DM Sans,sans-serif',fontSize:11,
              color: tab===t.id ? C.gold : C.textMuted,
              borderBottom: tab===t.id ? `2px solid ${C.gold}` : '2px solid transparent',
              transition:'all 0.2s',
            }}>{t.label}</div>
          ))}
        </div>
      </div>

      <div style={{padding: isDesktop ? '16px 24px 0' : '16px 16px 0'}}>
        {tab === 'inbox' && (
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
                background:C.gold,border:'none',borderRadius:7,
                width:34,height:34,cursor:'pointer',
                fontFamily:'DM Sans,sans-serif',fontSize:20,color:'#09070F',
                display:'flex',alignItems:'center',justifyContent:'center',lineHeight:1}}>+</button>
            </div>
            {inbox.length === 0
              ? <div style={{textAlign:'center',padding:'48px 0',
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

        {tab === 'projects' && EU.gtd.projects.map(p => {
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

        {tab === 'contexts' && (
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

        {tab === 'review' && (
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
                    <polyline points="2,5 4.5,8 8,2" stroke="#09070F" strokeWidth={1.5}
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
// PROFILE SCREEN
// ═══════════════════════════════════════════════════════════
function ProfileScreen({ appState, isDesktop }) {
  const { level, xp, xpNext, totalXP, modules } = appState;
  const lv = EU.levels[level - 1];
  const xpPct = xpNext ? xp / xpNext : 1;

  return (
    <div style={{minHeight:'100vh', paddingBottom: isDesktop ? 48 : 100}}>
      <div style={{padding: isDesktop ? '28px 24px 0' : '16px 20px 0'}}>
        <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,letterSpacing:'0.2em',
          color:C.gold,textTransform:'uppercase',opacity:0.6,marginBottom:4}}>ΑΥΤΟΣ</div>
        <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:28,
          fontWeight:600,color:C.text,letterSpacing:'0.05em',marginBottom:20}}>Perfil</div>
      </div>

      {/* Level showcase */}
      <div style={{padding:'0 16px 20px'}}>
        <div style={{
          background:'linear-gradient(135deg,#1C1830,#110F20)',
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
      <div style={{padding: isDesktop ? '0 24px' : '0 16px', display:'grid', gridTemplateColumns: isDesktop ? '1fr 1fr 1fr 1fr' : '1fr 1fr', gap:8, marginBottom:20}}>
        {[
          {label:'XP Total',      val: totalXP.toLocaleString()},
          {label:'Racha Mayor',   val:'33 días'},
          {label:'Hoy',           val:`${modules.filter(m=>m.done).length}/${modules.length} mods`},
          {label:'Semanas activo',val:'12'},
        ].map(s => (
          <div key={s.label} style={{background:C.card,
            border:'1px solid rgba(201,168,76,0.1)',borderRadius:12,padding:'14px'}}>
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
              color: lv.n < level ? '#09070F' : C.gold,
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
  HomeScreen, CommandCenterScreen, ModuleDetailScreen, GTDScreen, ProfileScreen,
});
