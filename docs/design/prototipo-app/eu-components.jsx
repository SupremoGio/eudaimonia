// EUDAIMONIA — UI Primitives
const { useState, useEffect } = React;
const C = window.EU.c;

// ─── Greek Column XP Visualizer ────────────────────────────
function GreekColumn({ level = 3, xpPct = 0.65, size = 110 }) {
  const totalDrums = 10;
  const h = size * 1.4;
  const cx = size / 2;
  const baseShaftW = size * 0.26;
  const shaftTop = h * 0.07;
  const shaftBot = h * 0.80;
  const shaftH = shaftBot - shaftTop;
  const drumH = shaftH / totalDrums;
  const capW = size * 0.42;
  const baseW = size * 0.50;
  const uid = `col${size}${level}`;

  return (
    <svg width={size} height={h} viewBox={`0 0 ${size} ${h}`} style={{overflow:'visible'}}>
      <defs>
        <linearGradient id={`gg${uid}`} x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="#7A5520"/>
          <stop offset="50%" stopColor="#C9A84C"/>
          <stop offset="100%" stopColor="#F0D880"/>
        </linearGradient>
        <linearGradient id={`gd${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1E1B2A"/>
          <stop offset="100%" stopColor="#131120"/>
        </linearGradient>
        <filter id={`glow${uid}`} x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="5" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id={`sglow${uid}`} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="2.5" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      {/* Drums — i=0 top, i=9 bottom */}
      {Array.from({length: totalDrums}).map((_, i) => {
        const fromBottom = totalDrums - 1 - i;
        const filled = fromBottom < level;
        const isCurrent = fromBottom === level - 1;
        // Entasis (slight column bulge)
        const entasis = 1 + Math.sin(Math.PI * ((fromBottom + 0.5) / totalDrums)) * 0.14;
        const w = baseShaftW * entasis;
        const y = shaftTop + i * drumH;
        return (
          <g key={i}>
            <rect
              x={cx - w/2} y={y + 0.5} width={w} height={drumH - 1} rx={0.8}
              fill={filled ? `url(#gg${uid})` : `url(#gd${uid})`}
              stroke={filled ? 'rgba(201,168,76,0.45)' : 'rgba(201,168,76,0.06)'}
              strokeWidth={0.5}
              filter={isCurrent ? `url(#sglow${uid})` : undefined}
            />
            {/* Fluting */}
            {[0.28, 0.5, 0.72].map((fx, fi) => (
              <line key={fi}
                x1={cx - w/2 + w*fx} y1={y+1.5}
                x2={cx - w/2 + w*fx} y2={y+drumH-1.5}
                stroke={filled ? 'rgba(255,210,80,0.1)' : 'rgba(255,255,255,0.025)'}
                strokeWidth={0.5}
              />
            ))}
            {/* XP partial fill on current drum */}
            {isCurrent && xpPct > 0 && (
              <rect
                x={cx - w/2 + 0.5} y={y + 0.5}
                width={(w - 1) * xpPct} height={drumH - 1}
                rx={0.8} fill="rgba(240,216,128,0.5)"
              />
            )}
          </g>
        );
      })}

      {/* Capital — echinus */}
      <ellipse cx={cx} cy={shaftTop + 1.5}
        rx={baseShaftW * 0.75} ry={3}
        fill={`url(#gg${uid})`} opacity={0.45}/>
      {/* Capital — abacus */}
      <rect x={cx - capW/2} y={shaftTop - h*0.045} width={capW} height={h*0.045} rx={1}
        fill={level >= 10 ? `url(#gg${uid})` : '#1C1829'}
        stroke="rgba(201,168,76,0.25)" strokeWidth={0.5}/>
      {/* Entablature */}
      <rect x={cx - capW*0.56} y={shaftTop - h*0.06} width={capW*1.12} height={h*0.014} rx={0.5}
        fill="#191525" stroke="rgba(201,168,76,0.15)" strokeWidth={0.5}/>

      {/* Base — torus */}
      <rect x={cx - baseShaftW*0.65} y={shaftBot} width={baseShaftW*1.3} height={h*0.03} rx={1}
        fill="#1E1B2A" stroke="rgba(201,168,76,0.14)" strokeWidth={0.5}/>
      {/* Stylobate steps */}
      <rect x={cx - baseW*0.5} y={shaftBot + h*0.031} width={baseW} height={h*0.038} rx={1}
        fill="#1A1726" stroke="rgba(201,168,76,0.1)" strokeWidth={0.5}/>
      <rect x={cx - baseW*0.62} y={shaftBot + h*0.069} width={baseW*1.24} height={h*0.038} rx={1}
        fill="#181524" stroke="rgba(201,168,76,0.08)" strokeWidth={0.5}/>
    </svg>
  );
}

// ─── Progress Ring ──────────────────────────────────────────
function ProgressRing({ pct = 0, size = 44, stroke = 3, color = C.gold }) {
  const r = (size - stroke * 2) / 2;
  const circ = 2 * Math.PI * r;
  const cx = size / 2;
  return (
    <svg width={size} height={size} style={{display:'block'}}>
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="rgba(201,168,76,0.07)" strokeWidth={stroke}/>
      <circle cx={cx} cy={cx} r={r} fill="none"
        stroke={color} strokeWidth={stroke}
        strokeDasharray={`${circ * Math.min(1, pct)} ${circ}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cx})`}
        style={{transition:'stroke-dasharray 0.8s ease'}}/>
    </svg>
  );
}

// ─── Module Card ───────────────────────────────────────────
function ModuleCard({ mod, onClick, small = false }) {
  const [hov, setHov] = useState(false);
  const acc = `oklch(65% 0.15 ${mod.hue})`;
  const accBg = `oklch(18% 0.04 ${mod.hue})`;
  const accBorder = `oklch(35% 0.09 ${mod.hue})`;

  return (
    <div onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? C.cardHover : C.card,
        border: `1px solid ${hov ? accBorder : C.goldBorder}`,
        borderRadius: 14, padding: small ? '12px 14px' : '16px 15px',
        cursor:'pointer', position:'relative', overflow:'hidden',
        transition:'all 0.25s ease',
        boxShadow: hov ? `0 8px 32px rgba(0,0,0,0.45), 0 0 24px ${accBg}` : '0 2px 14px rgba(0,0,0,0.32)',
      }}>
      {/* Corner glow */}
      <div style={{position:'absolute',top:0,right:0,width:70,height:70,
        background:`radial-gradient(circle at top right, ${accBg}, transparent 70%)`,
        pointerEvents:'none'}}/>
      {/* Done dot */}
      {mod.done && <div style={{position:'absolute',top:11,left:12,
        width:6,height:6,borderRadius:'50%',
        background:C.success, boxShadow:`0 0 7px ${C.success}`}}/>}
      {/* Streak */}
      <div style={{position:'absolute',top:10,right:12,
        fontFamily:'DM Sans,sans-serif',fontSize:9,color:acc,opacity:0.75,
        letterSpacing:'0.05em'}}>
        {mod.streak}d ◆
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:small?13:15,
        fontWeight:600,color:C.text,letterSpacing:'0.08em',marginTop:small?0:2}}>
        {mod.name}
      </div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:acc,
        letterSpacing:'0.1em',textTransform:'uppercase',marginTop:3,lineHeight:1.3}}>
        {mod.concept}
      </div>
      {!small && <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,
        color:C.textMuted,marginTop:6}}>{mod.desc}</div>}
    </div>
  );
}

// ─── Habit Row ────────────────────────────────────────────
function HabitRow({ label, done, onToggle, xp = 10, accent = C.gold }) {
  const [burst, setBurst] = useState(false);
  const handle = () => {
    if (!done) { setBurst(true); setTimeout(() => setBurst(false), 700); }
    onToggle();
  };
  const dirs = [[28,-28],[38,0],[28,28],[0,38],[-28,28],[-38,0],[-28,-28],[0,-38]];
  return (
    <div style={{display:'flex',alignItems:'center',gap:12,padding:'11px 0',
      borderBottom:'1px solid rgba(201,168,76,0.06)',position:'relative'}}>
      <div onClick={handle} style={{
        width:22,height:22,borderRadius:6,flexShrink:0,cursor:'pointer',
        border:`1.5px solid ${done ? accent : 'rgba(201,168,76,0.22)'}`,
        background: done ? accent : 'transparent',
        display:'flex',alignItems:'center',justifyContent:'center',
        transition:'all 0.2s',
        boxShadow: done ? `0 0 10px ${accent}55` : 'none',
      }}>
        {done && <svg width={11} height={11} viewBox="0 0 11 11">
          <polyline points="2,5.5 4.5,8.5 9,2.5" stroke="#09070F"
            strokeWidth={1.8} fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>}
      </div>
      <span style={{flex:1,fontFamily:'DM Sans,sans-serif',fontSize:13,
        color:done?C.textMuted:C.text,textDecoration:done?'line-through':'none',
        transition:'all 0.3s'}}>{label}</span>
      <span style={{fontFamily:'DM Sans,sans-serif',fontSize:9,color:C.textMuted}}>+{xp} XP</span>
      {burst && dirs.map(([dx,dy],i) => (
        <div key={i} style={{
          position:'absolute',left:11,top:'50%',
          width:5,height:5,borderRadius:'50%',
          background:`oklch(75% 0.18 ${45+i*20})`,
          transform:`translate(${dx}px,${dy-10}px)`,
          opacity:0, animation:`euBurst 0.65s ease-out forwards`,
          animationDelay:`${i*0.02}s`, pointerEvents:'none',
        }}/>
      ))}
    </div>
  );
}

// ─── Quote Display ────────────────────────────────────────
function QuoteDisplay({ quote }) {
  return (
    <div style={{
      padding:'18px 18px 16px',
      background:'rgba(201,168,76,0.04)',
      border:'1px solid rgba(201,168,76,0.1)',
      borderLeft:'3px solid rgba(201,168,76,0.45)',
      borderRadius:'0 10px 10px 0',
    }}>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
        fontSize:16,lineHeight:1.6,color:C.text,marginBottom:10,textWrap:'pretty'}}>
        "{quote.text}"
      </div>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:9,
        letterSpacing:'0.12em',color:C.gold,textTransform:'uppercase',opacity:0.75}}>
        — {quote.author}
      </div>
    </div>
  );
}

// ─── Bottom Nav ───────────────────────────────────────────
function BottomNav({ active, onChange }) {
  const tabs = [
    { id:'home', label:'Ἀρχή', sub:'Inicio' },
    { id:'modules', label:'Κόσμος', sub:'Módulos' },
    { id:'gtd', label:'Συνήθεια', sub:'ACTA DIURNA' },
    { id:'profile', label:'Αὐτός', sub:'Perfil' },
  ];
  return (
    <div style={{
      position:'fixed',bottom:0,left:'50%',transform:'translateX(-50%)',
      width:'100%',maxWidth:430,
      background:'rgba(9,7,15,0.97)',
      backdropFilter:'blur(24px)',
      borderTop:'1px solid rgba(201,168,76,0.12)',
      display:'flex',
      paddingBottom:'env(safe-area-inset-bottom,8px)',
      zIndex:200,
    }}>
      {tabs.map(t => (
        <div key={t.id} onClick={() => onChange(t.id)} style={{
          flex:1,display:'flex',flexDirection:'column',alignItems:'center',
          padding:'10px 4px 6px',cursor:'pointer',
        }}>
          <div style={{
            fontFamily:'Cormorant Garamond,serif',fontSize:17,
            color: active===t.id ? C.gold : C.textMuted,
            transition:'all 0.25s',lineHeight:1,
          }}>{t.label}</div>
          <div style={{
            fontFamily:'DM Sans,sans-serif',fontSize:8,letterSpacing:'0.1em',
            textTransform:'uppercase',marginTop:3,
            color: active===t.id ? C.gold : C.textMuted,
            opacity: active===t.id ? 1 : 0.45,
            transition:'all 0.25s',
          }}>{t.sub}</div>
          {active===t.id && <div style={{
            width:20,height:2,borderRadius:1,
            background:C.gold,marginTop:4,
            boxShadow:`0 0 6px ${C.gold}`,
          }}/>}
        </div>
      ))}
    </div>
  );
}

// ─── Level Up Modal ───────────────────────────────────────
function LevelUpModal({ level, onClose }) {
  const lv = EU.levels[level - 1];
  return (
    <div style={{
      position:'fixed',inset:0,zIndex:999,
      background:'rgba(9,7,15,0.95)',
      display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',
      padding:24,
      animation:'euFadeIn 0.5s ease',
    }}>
      {/* Radial gold burst */}
      <div style={{
        position:'absolute',inset:0,
        background:`radial-gradient(ellipse at center, rgba(201,168,76,0.12) 0%, transparent 65%)`,
        pointerEvents:'none',
      }}/>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,letterSpacing:'0.25em',
        color:C.gold,textTransform:'uppercase',marginBottom:12,opacity:0.7}}>
        ¡SUBISTE DE NIVEL!
      </div>
      <GreekColumn level={level} xpPct={0} size={120}/>
      <div style={{fontFamily:'DM Sans,sans-serif',fontSize:10,letterSpacing:'0.2em',
        color:C.gold,marginTop:20,marginBottom:6,opacity:0.65}}>
        NIVEL {level}
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontSize:44,fontWeight:600,
        color:C.text,letterSpacing:'0.08em',textAlign:'center',
        animation:'euScaleIn 0.6s ease 0.2s both'}}>
        {lv?.name}
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif',fontStyle:'italic',
        fontSize:18,color:C.textSub,marginTop:6,marginBottom:32}}>
        {lv?.sub}
      </div>
      <button onClick={onClose} style={{
        background:'transparent',border:`1.5px solid rgba(201,168,76,0.4)`,
        borderRadius:10,padding:'12px 32px',
        fontFamily:'DM Sans,sans-serif',fontSize:12,letterSpacing:'0.15em',
        color:C.gold,cursor:'pointer',textTransform:'uppercase',
        transition:'all 0.2s',
      }}>
        CONTINUAR
      </button>
    </div>
  );
}

Object.assign(window, {
  GreekColumn, ProgressRing, ModuleCard, HabitRow, QuoteDisplay, BottomNav, LevelUpModal,
});
