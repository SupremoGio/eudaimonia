// EUDAIMONIA — App State & Root
const { useState, useReducer, useEffect } = React;

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

function App() {
  const [state, dispatch] = useReducer(reducer, null, () => loadState() || initial);
  const [tab, setTab] = useState('home');

  useEffect(() => {
    localStorage.setItem(SAVE_KEY, JSON.stringify(state));
  }, [state]);

  useEffect(() => {
    if (state._tab && state._tab !== tab) { setTab(state._tab); }
  }, [state._tab]);

  const appDispatch = (action) => {
    if (action.type === 'SET_TAB') setTab(action.tab);
    dispatch(action);
  };

  const props = { appState: state, dispatch: appDispatch };
  const openMod = state.openModuleId
    ? state.modules.find(m => m.id === state.openModuleId)
    : null;

  return (
    <div style={{
      maxWidth: 430, margin: '0 auto', minHeight: '100vh',
      background: EU.c.deep, position: 'relative',
      fontFamily: 'DM Sans, sans-serif',
    }}>
      {/* Screens */}
      <div>
        {openMod ? (
          <ModuleDetailScreen mod={openMod} {...props} />
        ) : tab === 'home'    ? <HomeScreen {...props} />
          : tab === 'modules' ? <CommandCenterScreen {...props} />
          : tab === 'gtd'     ? <GTDScreen {...props} />
          : <ProfileScreen {...props} />
        }
      </div>

      {/* Level-up modal */}
      {state.leveledUp && (
        <LevelUpModal level={state.level} onClose={() => dispatch({ type: 'CLEAR_LEVELUP' })} />
      )}

      {/* Bottom nav — hide when module is open */}
      {!openMod && <BottomNav active={tab} onChange={setTab} />}
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
      position: 'fixed', bottom: 90, right: 16, zIndex: 9000,
      background: '#1A1627', border: '1px solid rgba(201,168,76,0.25)',
      borderRadius: 14, padding: '16px', width: 220,
      boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
      fontFamily: 'DM Sans, sans-serif',
    }}>
      <div style={{ fontSize: 10, letterSpacing: '0.15em', color: EU.c.gold,
        textTransform: 'uppercase', marginBottom: 14 }}>Tweaks</div>

      <label style={{ display: 'block', marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: EU.c.textMuted, marginBottom: 5 }}>
          Demo Nivel: {tweaks.levelDemo}
        </div>
        <input type="range" min={1} max={10} value={tweaks.levelDemo}
          onChange={e => onChange('levelDemo', +e.target.value)}
          style={{ width: '100%', accentColor: EU.c.gold }} />
      </label>

      <label style={{ display: 'block', marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: EU.c.textMuted, marginBottom: 5 }}>
          Color acento (hue): {tweaks.accentHue}°
        </div>
        <input type="range" min={0} max={360} value={tweaks.accentHue}
          onChange={e => onChange('accentHue', +e.target.value)}
          style={{ width: '100%', accentColor: EU.c.gold }} />
      </label>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
        <input type="checkbox" checked={tweaks.showStreak}
          onChange={e => onChange('showStreak', e.target.checked)}
          style={{ accentColor: EU.c.gold }} />
        <span style={{ fontSize: 11, color: EU.c.textSub }}>Mostrar rachas</span>
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
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
  }, []);

  const handleTweak = (key, val) => {
    const next = { ...tweaks, [key]: val };
    setTweaks(next);
    window.parent.postMessage({ type: '__edit_mode_set_keys', edits: next }, '*');
  };

  return (
    <>
      <App tweaks={tweaks} />
      <TweaksPanel tweaks={tweaks} onChange={handleTweak} visible={tweakVisible} />
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Root />);
