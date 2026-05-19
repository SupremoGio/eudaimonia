// EUDAIMONIA — App State & Root
const { useState, useReducer, useEffect, useMemo } = React;
const C = window.EU.getColors();

function _xpStateFromTotal(totalXP) {
  const thr = EU.levelThresholds; // [0,200,500,1000,1800,2700,3600,4400,5000,5500]
  let level = 1;
  for (let i = 0; i < thr.length; i++) {
    if (totalXP >= thr[i]) level = i + 1; else break;
  }
  level = Math.max(1, Math.min(10, level));
  const cur  = thr[level - 1] || 0;
  const next = level < 10 ? (thr[level] || 5500) : 5500;
  return { level, xp: totalXP - cur, xpNext: level < 10 ? (next - cur) : null };
}

function initFromServer() {
  const d = window.__EUDAIMONIA_DATA__ || {};
  const totalXP = d.total_xp || 0;
  const { level, xp, xpNext } = _xpStateFromTotal(totalXP);
  // Merge server modules (dynamic streak/done) with static route info
  const serverMods = Array.isArray(d.modules) && d.modules.length > 0 ? d.modules : null;
  const modules = serverMods
    ? EU.modules.map(m => { const s = serverMods.find(sm => sm.id === m.id); return s ? {...m, streak: s.streak, done: s.done} : m; })
    : EU.modules;
  return { level, xp, xpNext, totalXP, modules, openModuleId: null, leveledUp: false };
}

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_XP': {
      const totalXP = state.totalXP + action.amount;
      const next = _xpStateFromTotal(totalXP);
      const leveledUp = next.level > state.level;
      return { ...state, ...next, totalXP, leveledUp };
    }
    case 'CLEAR_LEVELUP': return { ...state, leveledUp: false };
    case 'OPEN_MODULE':   return { ...state, openModuleId: action.id };
    case 'CLOSE_MODULE':  return { ...state, openModuleId: null };
    case 'SET_TAB':       return { ...state, _tab: action.tab };
    default: return state;
  }
}

// ── Responsive hook ───────────────────────────────────────
function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 768);
  useEffect(() => {
    const handler = () => setIsDesktop(window.innerWidth >= 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isDesktop;
}

// ── Desktop Sidebar Nav ───────────────────────────────────
function SideNav({ active, onChange }) {
  const groups = [
    { title: 'HOY',     tabs: [
      { id:'home', label:'Ἀρχή', sub:'Inicio' },
      { id:'acta', label:'Acta', sub:'Diurna' },
    ]},
    { title: 'MÓDULOS', tabs: [
      { id:'modules', label:'Κόσμος', sub:'Módulos' },
    ]},
    { title: 'SISTEMA', tabs: [
      { id:'profile', label:'Αὐτός', sub:'Perfil' },
    ]},
  ];
  return (
    <div style={{
      width: 210, flexShrink: 0,
      background: EU.rgba('deep', 0.99),
      borderRight: '1px solid rgba(201,168,76,0.1)',
      position: 'fixed', top: 0, left: 0, bottom: 0,
      display: 'flex', flexDirection: 'column',
      zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{padding: '28px 22px 24px', borderBottom: '1px solid rgba(201,168,76,0.08)'}}>
        <div style={{fontFamily:'DM Sans,sans-serif', fontSize:8, letterSpacing:'0.28em',
          color:C.gold, opacity:0.55, textTransform:'uppercase', marginBottom:5}}>
          SISTEMA PERSONAL
        </div>
        <div style={{fontFamily:'Cormorant Garamond,serif', fontSize:20,
          color:C.text, letterSpacing:'0.14em', fontWeight:600}}>
          EUDAIMONIA
        </div>
      </div>

      {/* Nav groups */}
      <div style={{flex:1, paddingTop:8, overflowY:'auto'}}>
        {groups.map(g => (
          <div key={g.title}>
            <div style={{fontSize:11, letterSpacing:'0.2em', color:C.textMuted,
              padding:'14px 22px 6px', textTransform:'uppercase', opacity:0.55}}>
              {g.title}
            </div>
            {g.tabs.map(t => {
              const active_ = active === t.id;
              return (
                <div key={t.id} onClick={() => onChange(t.id)} style={{
                  padding: '11px 22px',
                  cursor: 'pointer',
                  borderLeft: `2.5px solid ${active_ ? C.gold : 'transparent'}`,
                  background: active_ ? 'rgba(201,168,76,0.05)' : 'transparent',
                  transition: 'all 0.2s',
                }}>
                  <div style={{fontFamily:'Cormorant Garamond,serif', fontSize:20,
                    color: active_ ? C.gold : C.textMuted,
                    transition:'color 0.2s', lineHeight:1}}>
                    {t.label}
                  </div>
                  <div style={{fontFamily:'DM Sans,sans-serif', fontSize:11,
                    letterSpacing:'0.12em', textTransform:'uppercase', marginTop:3,
                    color: active_ ? C.gold : C.textMuted,
                    opacity: active_ ? 0.75 : 0.35, transition:'all 0.2s'}}>
                    {t.sub}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Theme toggle */}
      <div style={{padding:'12px 22px 16px', borderTop:'1px solid rgba(201,168,76,0.07)'}}>
        <button onClick={() => window.euToggleTheme()} style={{
          display:'flex', alignItems:'center', gap:8,
          background:'transparent', border:`1px solid ${C.goldBorder}`,
          borderRadius:8, padding:'7px 12px', cursor:'pointer',
          fontFamily:'DM Sans,sans-serif', fontSize:10, color:C.textMuted,
          letterSpacing:'0.08em', width:'100%',
        }}>
          <span style={{fontSize:14, lineHeight:1}}>
            {document.documentElement.classList.contains('light') ? '☀' : '☽'}
          </span>
          <span>{document.documentElement.classList.contains('light') ? 'Modo día' : 'Modo noche'}</span>
        </button>
      </div>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────
function App() {
  const [state, dispatch] = useReducer(reducer, null, initFromServer);
  const [tab, setTab] = useState(() => {
    const p = new URLSearchParams(window.location.search);
    const t = p.get('tab');
    return ['home','modules','acta','profile'].includes(t) ? t : 'home';
  });
  const isDesktop = useIsDesktop();

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const open = p.get('open');
    if (open && state.modules.find(m => m.id === open)) {
      dispatch({ type: 'OPEN_MODULE', id: open });
    }
  }, []);

  const appDispatch = (action) => {
    if (action.type === 'SET_TAB') setTab(action.tab);
    dispatch(action);
  };

  // Closing a module must happen whenever the user switches tabs
  const handleTabChange = (id) => {
    dispatch({ type: 'CLOSE_MODULE' });
    setTab(id);
  };

  const [cmdkOpen, setCmdkOpen] = useState(false);

  // ⌘K global shortcut + custom event from HomeScreen header button
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdkOpen(o => !o);
      }
    };
    const onEv = () => setCmdkOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('eu:open-cmdk', onEv);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('eu:open-cmdk', onEv);
    };
  }, []);

  const logActivityFromApp = (key) => {
    const updated = (window.EU._server.activities || []).map(a =>
      a.key === key ? {...a, done: !a.done} : a
    );
    window.EU._server.activities = updated;
    fetch('/actividades/api/activity/log', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({key}),
    })
    .then(r => r.json())
    .then(data => {
      if (data.gam && (data.gam.xp_delta || data.gam.xp))
        dispatch({type:'ADD_XP', amount: data.gam.xp_delta || data.gam.xp});
    })
    .catch(() => {});
  };

  const cmdkItems = useMemo(() => {
    const pendingActs = (window.EU._server?.activities || [])
      .filter(a => !a.done)
      .slice(0, 20);
    return [
      { i:'⌂', label:'Ir a Inicio',         sub:'Dashboard',      section:'nav', run: () => handleTabChange('home') },
      { i:'✦', label:'Ir a Acta Diurna',    sub:'Actividades',    section:'nav', run: () => handleTabChange('acta') },
      { i:'◆', label:'Ir a Módulos',         sub:'Command Center', section:'nav', run: () => handleTabChange('modules') },
      { i:'◎', label:'Ir a Perfil',          sub:'Sistema',        section:'nav', run: () => handleTabChange('profile') },
      { i:'◐', label:'Cambiar tema',         sub:'Día / Noche',    section:'sys', keys:['⇧','T'], run: () => window.euToggleTheme() },
      { i:'🏆', label:'Ver Logros',          sub:'Sistema',        section:'sys', run: () => { location.href = '/logros'; } },
      ...pendingActs.map(a => ({
        i: '✓',
        label: `Registrar: ${a.label} (+${a.pts} XP)`,
        sub:   `Acta · ${a.cat}`,
        section: 'act',
        run:   () => logActivityFromApp(a.key),
      })),
    ];
  }, [state.totalXP]);

  const props = { appState: state, dispatch: appDispatch, isDesktop };
  const openMod = state.openModuleId
    ? state.modules.find(m => m.id === state.openModuleId)
    : null;

  const screen = openMod
    ? <ModuleDetailScreen mod={openMod} {...props} />
    : tab === 'home'    ? <HomeScreen {...props} />
    : tab === 'modules' ? <CommandCenterScreen {...props} />
    : tab === 'acta'    ? <ActaDiurnaScreen {...props} />
    : <ProfileScreen {...props} />;

  if (isDesktop) {
    return (
      <div style={{display:'flex', minHeight:'100vh', background:C.deep}}>
        <SideNav active={tab} onChange={handleTabChange} />
        <div style={{marginLeft:210, flex:1, minHeight:'100vh'}}>
          <div style={{maxWidth:900, margin:'0 auto', padding:'0 8px'}}>
            {screen}
          </div>
        </div>
        {state.leveledUp && (
          <LevelUpModal level={state.level} onClose={() => dispatch({type:'CLEAR_LEVELUP'})} />
        )}
        <CommandPalette open={cmdkOpen} onClose={() => setCmdkOpen(false)} items={cmdkItems} />
      </div>
    );
  }

  return (
    <div style={{
      maxWidth:430, margin:'0 auto', minHeight:'100vh',
      background:C.deep, position:'relative',
      fontFamily:'DM Sans, sans-serif',
    }}>
      {screen}
      {state.leveledUp && (
        <LevelUpModal level={state.level} onClose={() => dispatch({type:'CLEAR_LEVELUP'})} />
      )}
      {!openMod && <BottomNav active={tab} onChange={handleTabChange} />}
      <CommandPalette open={cmdkOpen} onClose={() => setCmdkOpen(false)} items={cmdkItems} />
    </div>
  );
}

// ── Tweaks ────────────────────────────────────────────────
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accentHue": 45,
  "levelDemo": 3,
  "showStreak": true
}/*EDITMODE-END*/;

function TweaksPanel({ tweaks, onChange, visible }) {
  if (!visible) return null;
  return (
    <div style={{
      position:'fixed', bottom:90, right:16, zIndex:9000,
      background:C.card, border:'1px solid rgba(201,168,76,0.25)',
      borderRadius:14, padding:'16px', width:220,
      boxShadow:'0 8px 32px rgba(0,0,0,0.6)',
      fontFamily:'DM Sans, sans-serif',
    }}>
      <div style={{fontSize:10, letterSpacing:'0.15em', color:C.gold,
        textTransform:'uppercase', marginBottom:14}}>Tweaks</div>
      <label style={{display:'block', marginBottom:12}}>
        <div style={{fontSize:10, color:C.textMuted, marginBottom:5}}>
          Demo Nivel: {tweaks.levelDemo}
        </div>
        <input type="range" min={1} max={10} value={tweaks.levelDemo}
          onChange={e => onChange('levelDemo', +e.target.value)}
          style={{width:'100%', accentColor:C.gold}} />
      </label>
      <label style={{display:'block', marginBottom:12}}>
        <div style={{fontSize:10, color:C.textMuted, marginBottom:5}}>
          Color acento (hue): {tweaks.accentHue}°
        </div>
        <input type="range" min={0} max={360} value={tweaks.accentHue}
          onChange={e => onChange('accentHue', +e.target.value)}
          style={{width:'100%', accentColor:C.gold}} />
      </label>
      <label style={{display:'flex', alignItems:'center', gap:8, cursor:'pointer'}}>
        <input type="checkbox" checked={tweaks.showStreak}
          onChange={e => onChange('showStreak', e.target.checked)}
          style={{accentColor:C.gold}} />
        <span style={{fontSize:11, color:C.textSub}}>Mostrar rachas</span>
      </label>
    </div>
  );
}

function Root() {
  const [tweaks, setTweaks] = useState(TWEAK_DEFAULTS);
  const [tweakVisible, setTweakVisible] = useState(false);

  useEffect(() => {
    window.addEventListener('message', e => {
      if (e.data?.type === '__activate_edit_mode')   setTweakVisible(true);
      if (e.data?.type === '__deactivate_edit_mode') setTweakVisible(false);
    });
    window.parent.postMessage({ type:'__edit_mode_available' }, '*');
  }, []);

  const handleTweak = (key, val) => {
    const next = { ...tweaks, [key]: val };
    setTweaks(next);
    window.parent.postMessage({ type:'__edit_mode_set_keys', edits:next }, '*');
  };

  return (
    <>
      <App tweaks={tweaks} />
      <TweaksPanel tweaks={tweaks} onChange={handleTweak} visible={tweakVisible} />
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Root />);
