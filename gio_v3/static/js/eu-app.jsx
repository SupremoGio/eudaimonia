// EUDAIMONIA — App State & Root
const { useState, useReducer, useEffect } = React;
const C = window.EU.c;

const SAVE_KEY = 'eudaimonia_v1';

const initial = {
  level: 3,
  xp: 186,
  xpNext: 250,
  totalXP: 636,
  modules: window.EU.modules,
  openModuleId: null,
};

function loadState() {
  try { const s = localStorage.getItem(SAVE_KEY); if (s) return JSON.parse(s); } catch {}
  return null;
}

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_XP': {
      let xp = state.xp + action.amount;
      let totalXP = state.totalXP + action.amount;
      let level = state.level;
      let xpNext = state.xpNext;
      let leveledUp = false;
      if (xpNext && xp >= xpNext) {
        level = Math.min(10, level + 1);
        xp = xp - xpNext;
        xpNext = EU.levels[level - 1]?.xpNext || null;
        leveledUp = true;
      }
      return { ...state, xp, xpNext, totalXP, level, leveledUp };
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
  const tabs = [
    { id:'home',    label:'Ἀρχή',      sub:'Inicio'   },
    { id:'modules', label:'Κόσμος',    sub:'Módulos'  },
    { id:'gtd',     label:'Συνήθεια',  sub:'Acta Diurna' },
    { id:'profile', label:'Αὐτός',     sub:'Perfil'   },
  ];
  return (
    <div style={{
      width: 210, flexShrink: 0,
      background: 'rgba(9,7,15,0.99)',
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

      {/* Nav items */}
      <div style={{flex:1, paddingTop:16}}>
        {tabs.map(t => {
          const active_ = active === t.id;
          return (
            <div key={t.id} onClick={() => onChange(t.id)} style={{
              padding: '13px 22px',
              cursor: 'pointer',
              borderLeft: `2.5px solid ${active_ ? C.gold : 'transparent'}`,
              background: active_ ? 'rgba(201,168,76,0.05)' : 'transparent',
              transition: 'all 0.2s',
            }}>
              <div style={{fontFamily:'Cormorant Garamond,serif', fontSize:22,
                color: active_ ? C.gold : C.textMuted,
                transition:'color 0.2s', lineHeight:1}}>
                {t.label}
              </div>
              <div style={{fontFamily:'DM Sans,sans-serif', fontSize:8.5,
                letterSpacing:'0.12em', textTransform:'uppercase', marginTop:3,
                color: active_ ? C.gold : C.textMuted,
                opacity: active_ ? 0.75 : 0.35, transition:'all 0.2s'}}>
                {t.sub}
              </div>
            </div>
          );
        })}
      </div>

      {/* Link al dashboard clásico */}
      <div style={{padding:'16px 22px', borderTop:'1px solid rgba(201,168,76,0.07)'}}>
        <a href="/classic" style={{fontFamily:'DM Sans,sans-serif', fontSize:9.5,
          color:C.textMuted, opacity:0.45, textDecoration:'none',
          letterSpacing:'0.08em', display:'flex', alignItems:'center', gap:5}}>
          ← Dashboard clásico
        </a>
      </div>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────
function App() {
  const [state, dispatch] = useReducer(reducer, null, () => {
    const saved = loadState();
    // Always use fresh server data for modules and clear transient state
    return saved
      ? { ...saved, modules: window.EU.modules, openModuleId: null }
      : initial;
  });
  const [tab, setTab] = useState('home');
  const isDesktop = useIsDesktop();

  useEffect(() => {
    // Don't persist transient UI state — always start fresh on reload
    const { _tab, openModuleId, ...toSave } = state;
    localStorage.setItem(SAVE_KEY, JSON.stringify(toSave));
  }, [state]);

  const appDispatch = (action) => {
    if (action.type === 'SET_TAB') setTab(action.tab);
    dispatch(action);
  };

  // Closing a module must happen whenever the user switches tabs
  const handleTabChange = (id) => {
    dispatch({ type: 'CLOSE_MODULE' });
    setTab(id);
  };

  const props = { appState: state, dispatch: appDispatch, isDesktop };
  const openMod = state.openModuleId
    ? state.modules.find(m => m.id === state.openModuleId)
    : null;

  const screen = openMod
    ? <ModuleDetailScreen mod={openMod} {...props} />
    : tab === 'home'    ? <HomeScreen {...props} />
    : tab === 'modules' ? <CommandCenterScreen {...props} />
    : tab === 'gtd'     ? <GTDScreen {...props} />
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
      background:'#1A1627', border:'1px solid rgba(201,168,76,0.25)',
      borderRadius:14, padding:'16px', width:220,
      boxShadow:'0 8px 32px rgba(0,0,0,0.6)',
      fontFamily:'DM Sans, sans-serif',
    }}>
      <div style={{fontSize:10, letterSpacing:'0.15em', color:EU.c.gold,
        textTransform:'uppercase', marginBottom:14}}>Tweaks</div>
      <label style={{display:'block', marginBottom:12}}>
        <div style={{fontSize:10, color:EU.c.textMuted, marginBottom:5}}>
          Demo Nivel: {tweaks.levelDemo}
        </div>
        <input type="range" min={1} max={10} value={tweaks.levelDemo}
          onChange={e => onChange('levelDemo', +e.target.value)}
          style={{width:'100%', accentColor:EU.c.gold}} />
      </label>
      <label style={{display:'block', marginBottom:12}}>
        <div style={{fontSize:10, color:EU.c.textMuted, marginBottom:5}}>
          Color acento (hue): {tweaks.accentHue}°
        </div>
        <input type="range" min={0} max={360} value={tweaks.accentHue}
          onChange={e => onChange('accentHue', +e.target.value)}
          style={{width:'100%', accentColor:EU.c.gold}} />
      </label>
      <label style={{display:'flex', alignItems:'center', gap:8, cursor:'pointer'}}>
        <input type="checkbox" checked={tweaks.showStreak}
          onChange={e => onChange('showStreak', e.target.checked)}
          style={{accentColor:EU.c.gold}} />
        <span style={{fontSize:11, color:EU.c.textSub}}>Mostrar rachas</span>
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
