// ── Command Palette ⌘K ───────────────────────────────────────────────────────
const { useState: _cpUseState, useMemo: _cpUseMemo, useEffect: _cpUseEffect } = React;

function CommandPalette({ open, onClose, items }) {
  const [q,   setQ]   = _cpUseState('');
  const [idx, setIdx] = _cpUseState(0);

  const filtered = _cpUseMemo(() => {
    if (!q.trim()) return items;
    const t = q.toLowerCase();
    return items.filter(it =>
      (it.label + ' ' + (it.sub || '')).toLowerCase().includes(t)
    );
  }, [items, q]);

  _cpUseEffect(() => { setIdx(0); }, [q]);

  _cpUseEffect(() => {
    if (!open) { setQ(''); setIdx(0); return; }
    const onKey = (e) => {
      if (e.key === 'Escape') { onClose(); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); setIdx(i => Math.min(filtered.length - 1, i + 1)); }
      else if (e.key === 'ArrowUp')   { e.preventDefault(); setIdx(i => Math.max(0, i - 1)); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        const sel = filtered[idx];
        if (sel) { sel.run(); onClose(); }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, filtered, idx, onClose]);

  if (!open) return null;

  const C2 = window.EU.getColors();

  // Group items into sections
  const navItems  = filtered.filter(i => i.section === 'nav');
  const sysItems  = filtered.filter(i => i.section === 'sys');
  const actItems  = filtered.filter(i => i.section === 'act');

  let globalIdx = 0;
  const renderItem = (item) => {
    const myIdx = globalIdx++;
    const isActive = myIdx === idx;
    return (
      <div key={item.label + myIdx}
        onMouseEnter={() => setIdx(myIdx)}
        onClick={() => { item.run(); onClose(); }}
        style={{
          display:'flex', alignItems:'center', gap:12,
          padding:'10px 16px', cursor:'pointer',
          borderLeft: isActive ? `2px solid ${C2.gold}` : '2px solid transparent',
          background: isActive ? 'color-mix(in srgb, var(--gold) 7%, transparent)' : 'transparent',
          transition:'background 0.12s',
        }}>
        <span style={{
          width:28, height:28, borderRadius:7, flexShrink:0,
          background:'color-mix(in srgb, var(--gold) 7%, transparent)', border:'1px solid color-mix(in srgb, var(--gold) 12%, transparent)',
          display:'flex', alignItems:'center', justifyContent:'center',
          fontSize:13, color:C2.gold,
        }}>{item.i}</span>
        <div style={{flex:1, minWidth:0}}>
          <div style={{fontSize:13, color:C2.text, overflow:'hidden',
            textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{item.label}</div>
          {item.sub && <div style={{fontSize:10, color:C2.textMuted, marginTop:1}}>{item.sub}</div>}
        </div>
        {item.keys && (
          <div style={{display:'flex', gap:3, flexShrink:0}}>
            {item.keys.map(k => (
              <kbd key={k} style={{
                background:'var(--gold-bg)', border:'1px solid var(--gold-border)',
                borderRadius:4, padding:'1px 5px', fontSize:10, color:C2.gold,
                fontFamily:'DM Sans,sans-serif',
              }}>{k}</kbd>
            ))}
          </div>
        )}
      </div>
    );
  };

  const SectionHeader = ({ title }) => (
    <div style={{
      fontSize:9, letterSpacing:'0.2em', textTransform:'uppercase',
      color:C2.textMuted, padding:'10px 16px 4px', opacity:0.55,
    }}>{title}</div>
  );

  return (
    <div onClick={onClose} style={{
      position:'fixed', inset:0, zIndex:900,
      background: 'color-mix(in srgb, var(--bg) 75%, transparent)',
      backdropFilter:'blur(8px)',
      display:'flex', alignItems:'flex-start', justifyContent:'center',
      padding:'15vh 16px 0',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width:'100%', maxWidth:580,
        background: 'var(--card)',
        border:`1px solid ${C2.goldBorder}`,
        borderRadius:12,
        boxShadow:'0 24px 80px rgba(0,0,0,0.6)',
        overflow:'hidden',
      }}>
        {/* Input row */}
        <div style={{
          display:'flex', alignItems:'center', gap:10,
          padding:'12px 16px',
          borderBottom:'1px solid var(--gold-bg)',
        }}>
          <span style={{color:C2.gold, fontSize:16, flexShrink:0}}>⌘</span>
          <input
            autoFocus
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Buscar acciones..."
            style={{
              flex:1, background:'transparent', border:'none', outline:'none',
              fontFamily:'DM Sans,sans-serif', fontSize:15, color:C2.text,
            }}
          />
          <kbd onClick={onClose} style={{
            background:'color-mix(in srgb, var(--gold) 7%, transparent)', border:'1px solid var(--gold-border)',
            borderRadius:5, padding:'2px 6px', fontSize:10, color:C2.textMuted,
            cursor:'pointer', fontFamily:'DM Sans,sans-serif',
          }}>ESC</kbd>
        </div>

        {/* Results */}
        <div style={{maxHeight:360, overflowY:'auto'}}>
          {filtered.length === 0 && (
            <div style={{padding:'24px 16px', textAlign:'center',
              fontSize:13, color:C2.textMuted}}>Sin resultados</div>
          )}
          {(() => { globalIdx = 0; return null; })()}
          {navItems.length > 0  && <><SectionHeader title="Ir a..."/>{navItems.map(renderItem)}</>}
          {sysItems.length > 0  && <><SectionHeader title="Sistema"/>{sysItems.map(renderItem)}</>}
          {actItems.length > 0  && <><SectionHeader title="Actividades pendientes"/>{actItems.map(renderItem)}</>}
        </div>

        {/* Footer */}
        <div style={{
          display:'flex', gap:16, padding:'8px 16px',
          borderTop:'1px solid color-mix(in srgb, var(--gold) 7%, transparent)',
          fontSize:10, color:C2.textMuted, opacity:0.6,
        }}>
          <span>↑↓ navegar</span>
          <span>⏎ seleccionar</span>
          <span>ESC cerrar</span>
        </div>
      </div>
    </div>
  );
}

window.CommandPalette = CommandPalette;
