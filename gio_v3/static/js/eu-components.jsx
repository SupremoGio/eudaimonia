// EUDAIMONIA — UI Primitives
const { useState, useEffect } = React;
const C = window.EU.getColors();

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
          <stop offset="0%"   style={{stopColor:'color-mix(in srgb, var(--gold) 60%, #000)'}}/>
          <stop offset="50%"  style={{stopColor:'var(--gold)'}}/>
          <stop offset="100%" style={{stopColor:'var(--gold-l)'}}/>
        </linearGradient>
        <linearGradient id={`gd${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   style={{stopColor:'var(--surf)'}}/>
          <stop offset="100%" style={{stopColor:'var(--bg)'}}/>
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
              stroke={filled ? 'var(--gold-glow)' : 'color-mix(in srgb, var(--gold) 6%, transparent)'}
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
        stroke="color-mix(in srgb, var(--gold) 25%, transparent)" strokeWidth={0.5}/>
      {/* Entablature */}
      <rect x={cx - capW*0.56} y={shaftTop - h*0.06} width={capW*1.12} height={h*0.014} rx={0.5}
        fill="#191525" stroke="var(--b)" strokeWidth={0.5}/>

      {/* Base — torus */}
      <rect x={cx - baseShaftW*0.65} y={shaftBot} width={baseShaftW*1.3} height={h*0.03} rx={1}
        fill="#1E1B2A" stroke="var(--b)" strokeWidth={0.5}/>
      {/* Stylobate steps */}
      <rect x={cx - baseW*0.5} y={shaftBot + h*0.031} width={baseW} height={h*0.038} rx={1}
        fill="#1A1726" stroke="var(--gold-bg)" strokeWidth={0.5}/>
      <rect x={cx - baseW*0.62} y={shaftBot + h*0.069} width={baseW*1.24} height={h*0.038} rx={1}
        fill="#181524" stroke="var(--gold-bg)" strokeWidth={0.5}/>
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
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="color-mix(in srgb, var(--gold) 7%, transparent)" strokeWidth={stroke}/>
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
      borderBottom:'1px solid color-mix(in srgb, var(--gold) 6%, transparent)',position:'relative'}}>
      <div onClick={handle} style={{
        width:22,height:22,borderRadius:6,flexShrink:0,cursor:'pointer',
        border:`1.5px solid ${done ? accent : 'color-mix(in srgb, var(--gold) 22%, transparent)'}`,
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
      background:'color-mix(in srgb, var(--gold) 4%, transparent)',
      border:'1px solid var(--gold-bg)',
      borderLeft:'3px solid var(--gold-glow)',
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
    { id:'home',    label:'Ἀρχή',     sub:'Inicio'   },
    { id:'modules', label:'Κόσμος',   sub:'Módulos'  },
    { id:'acta',    label:'Acta',     sub:'Diurna'   },
    { id:'profile', label:'Αὐτός',    sub:'Perfil'   },
  ];
  const isLight = document.documentElement.classList.contains('light');
  const SunIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4"/>
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41
               M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
    </svg>
  );
  const MoonIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  );
  return (
    <div style={{
      position:'fixed',bottom:0,left:'50%',transform:'translateX(-50%)',
      width:'100%',maxWidth:430,
      background:EU.rgba('deep', 0.97),
      backdropFilter:'blur(24px)',
      borderTop:'1px solid color-mix(in srgb, var(--gold) 12%, transparent)',
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
            fontFamily:'Cormorant Garamond,serif',fontSize:18,
            color: active===t.id ? C.gold : C.textMuted,
            transition:'all 0.25s',lineHeight:1,
          }}>{t.label}</div>
          <div style={{
            fontFamily:'DM Sans,sans-serif',fontSize:10,letterSpacing:'0.1em',
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

      {/* Theme toggle — 5th slot */}
      <div onClick={() => window.euToggleTheme()} style={{
        flex:1,display:'flex',flexDirection:'column',alignItems:'center',
        padding:'10px 4px 6px',cursor:'pointer',
        color: C.textMuted, transition:'color 0.25s',
      }}>
        <div style={{color: C.textMuted, lineHeight:1, transition:'all 0.25s'}}>
          {isLight ? <SunIcon/> : <MoonIcon/>}
        </div>
        <div style={{
          fontFamily:'DM Sans,sans-serif',fontSize:8,letterSpacing:'0.1em',
          textTransform:'uppercase',marginTop:3,
          color:C.textMuted,opacity:0.45,
        }}>{isLight ? 'Día' : 'Noche'}</div>
      </div>
    </div>
  );
}

// ─── Level Up Modal ───────────────────────────────────────
function LevelUpModal({ level, onClose, rewards = [] }) {
  const lv = EU.levels[level - 1];
  return (
    <div style={{
      position:'fixed', inset:0, zIndex:999,
      background: EU.rgba('deep', 0.95),
      display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
      padding:24,
      animation:'euFadeIn 0.5s ease',
    }}>
      {/* Pulsing radial burst */}
      <div style={{
        position:'absolute', inset:0,
        background:`radial-gradient(ellipse at center, var(--gold-border) 0%, transparent 60%)`,
        animation:'euGoldPulse 2.4s ease-in-out infinite',
        pointerEvents:'none',
      }}/>

      <div style={{fontFamily:'DM Sans,sans-serif', fontSize:10, letterSpacing:'0.25em',
        color:C.gold, textTransform:'uppercase', marginBottom:16, opacity:0.7}}>
        ¡SUBISTE DE NIVEL!
      </div>

      {/* Animated rising column */}
      <div style={{
        animation:'euLevelUpRise 1.2s ease-out',
        filter:'drop-shadow(0 0 24px var(--gold-glow))',
      }}>
        <GreekColumn level={level} xpPct={1} size={140}/>
      </div>

      <div style={{fontFamily:'DM Sans,sans-serif', fontSize:10, letterSpacing:'0.2em',
        color:C.gold, marginTop:20, marginBottom:6, opacity:0.65}}>
        NIVEL {level}
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif', fontSize:44, fontWeight:600,
        color:C.text, letterSpacing:'0.08em', textAlign:'center',
        animation:'euScaleIn 0.6s ease 0.3s both'}}>
        {lv?.name}
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif', fontStyle:'italic',
        fontSize:18, color:C.textSub, marginTop:6, marginBottom: rewards.length ? 18 : 32}}>
        {lv?.sub}
      </div>

      {/* Rewards pills — degrade bien si rewards=[] */}
      {rewards.length > 0 && (
        <div style={{display:'flex', gap:8, flexWrap:'wrap',
          justifyContent:'center', marginBottom:28, maxWidth:380}}>
          {rewards.map((r, i) => (
            <div key={i} style={{
              padding:'6px 14px',
              background:'var(--gold-bg)',
              border:`1px solid ${C.goldBorder}`,
              borderRadius:100,
              fontFamily:'DM Sans,sans-serif', fontSize:11,
              color:C.gold, letterSpacing:'0.06em',
              animation:`euScaleIn 0.5s ease ${0.5 + i * 0.15}s both`,
            }}>{r.icon} {r.label}</div>
          ))}
        </div>
      )}

      <button onClick={onClose} style={{
        background:'transparent', border:`1.5px solid var(--gold-glow)`,
        borderRadius:10, padding:'12px 32px',
        fontFamily:'DM Sans,sans-serif', fontSize:12, letterSpacing:'0.15em',
        color:C.gold, cursor:'pointer', textTransform:'uppercase',
        transition:'all 0.2s',
      }}>
        CONTINUAR
      </button>
    </div>
  );
}

// ─── Streak Heatmap ──────────────────────────────────────────
function StreakHeatmap({ days = 21, compact = false }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch(`/api/streak/heatmap?days=${days}`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {});
  }, [days]);

  if (!data) {
    return (
      <div style={{
        height: compact ? 60 : 100, borderRadius: 10,
        background: 'linear-gradient(90deg,color-mix(in srgb, var(--gold) 3%, transparent) 0%,var(--gold-bg) 50%,color-mix(in srgb, var(--gold) 3%, transparent) 100%)',
        backgroundSize: '200% 100%',
        animation: 'euShimmer 1.4s ease-in-out infinite',
      }}/>
    );
  }

  const maxXp     = Math.max(...data.days.map(d => d.xp), 1);
  const cellSize  = compact ? 14 : 18;
  const gap       = compact ? 3 : 4;
  const cols      = Math.ceil(days / 7);
  const todayStr  = data.days[data.days.length - 1].date;

  const cell = (xp) => {
    if (xp === 0) return { bg: 'color-mix(in srgb, var(--gold) 4%, transparent)', border: C.goldBorder };
    const t = xp / maxXp;
    return {
      bg:     `oklch(${50 + t * 25}% ${0.06 + t * 0.1} 80)`,
      border: `oklch(${55 + t * 25}% ${0.08 + t * 0.1} 80)`,
    };
  };

  return (
    <div>
      <div style={{display:'flex', justifyContent:'space-between',
        alignItems:'baseline', marginBottom:10}}>
        <div style={{fontSize:10, letterSpacing:'0.18em', color:C.textMuted,
          textTransform:'uppercase'}}>Últimos {days} días</div>
        <div style={{fontSize:11, color:C.gold, opacity:0.7}}>
          {data.days.filter(d => d.xp > 0).length} días activos
        </div>
      </div>
      <div style={{
        display:'grid',
        gridTemplateColumns:`repeat(${cols}, ${cellSize}px)`,
        gap, justifyContent:'start',
      }}>
        {data.days.map(d => {
          const s = cell(d.xp);
          const isToday = d.date === todayStr;
          return (
            <div key={d.date} title={`${d.date}: ${d.xp} XP`} style={{
              width: cellSize, height: cellSize, borderRadius: 4,
              background: s.bg, border: `1px solid ${s.border}`,
              boxShadow: isToday ? `0 0 8px ${C.gold}66` : 'none',
              transition: 'all 0.2s',
            }}/>
          );
        })}
      </div>
    </div>
  );
}

// ─── Achievement Sheet ────────────────────────────────────
function AchievementSheet({ achievement, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 6000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div style={{
      position:'fixed', inset:0, zIndex:998,
      background: EU.rgba('deep', 0.7),
      display:'flex', alignItems:'flex-end', justifyContent:'center',
      animation:'euFadeIn 0.3s ease',
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        background:'linear-gradient(180deg, #1C1830 0%, #110F20 100%)',
        border:`1px solid ${C.goldBorder}`,
        borderTopLeftRadius:24, borderTopRightRadius:24,
        padding:'32px 28px 40px',
        width:'100%', maxWidth:460,
        animation:'euAchievementRise 0.5s ease-out',
        boxShadow:'0 -20px 60px rgba(0,0,0,0.6)',
      }}>
        {/* Countdown bar */}
        <div style={{
          position:'absolute', top:0, left:0,
          height:3, borderRadius:'24px 24px 0 0',
          background:`linear-gradient(90deg,${C.gold},${C.goldLight})`,
          animation:'undoCountdown 6s linear forwards',
          width:'100%',
        }}/>
        <div style={{textAlign:'center'}}>
          <div style={{
            fontSize:64, lineHeight:1, marginBottom:14,
            filter:'drop-shadow(0 0 16px var(--gold-glow))',
          }}>
            {achievement.icon || '🏆'}
          </div>
          <div style={{fontSize:10, letterSpacing:'0.22em', color:C.gold,
            opacity:0.65, textTransform:'uppercase', marginBottom:6}}>
            Logro desbloqueado
          </div>
          <div style={{fontFamily:'Cormorant Garamond,serif', fontSize:28,
            fontWeight:600, color:C.text, letterSpacing:'0.04em', marginBottom:6}}>
            {achievement.name}
          </div>
          <div style={{fontFamily:'Cormorant Garamond,serif', fontStyle:'italic',
            fontSize:14, color:C.textSub, marginBottom:18, lineHeight:1.5}}>
            {achievement.description}
          </div>
          {achievement.xp > 0 && (
            <div style={{
              display:'inline-block', padding:'6px 16px',
              background:'var(--gold-bg)', border:`1px solid ${C.goldBorder}`,
              borderRadius:100, fontSize:13, color:C.gold,
              letterSpacing:'0.08em', marginBottom:22,
            }}>
              +{achievement.xp} XP
            </div>
          )}
          <div>
            <button onClick={onClose} style={{
              background:'transparent', border:`1.5px solid ${C.goldBorder}`,
              borderRadius:10, padding:'10px 36px',
              fontSize:12, letterSpacing:'0.15em', textTransform:'uppercase',
              color:C.gold, cursor:'pointer', transition:'all 0.2s',
            }}>Continuar</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Skeleton ──────────────────────────────────────────────
function Skeleton({ kind = 'card', width, height, style }) {
  const presets = {
    card:   { height: 80,  width: '100%',    borderRadius: 12 },
    line:   { height: 14,  width: '70%',     borderRadius: 6  },
    circle: { width:  44,  height: 44,        borderRadius: '50%' },
    title:  { height: 28,  width: '50%',     borderRadius: 6  },
  };
  const base = presets[kind] || presets.card;
  const s = {
    ...base,
    width:  width  || base.width,
    height: height || base.height,
    background: 'linear-gradient(90deg,color-mix(in srgb, var(--gold) 3%, transparent) 0%,var(--gold-bg) 50%,color-mix(in srgb, var(--gold) 3%, transparent) 100%)',
    backgroundSize: '200% 100%',
    animation: 'euShimmer 1.4s ease-in-out infinite',
    ...style,
  };
  return <div style={s}/>;
}

// ─── EmptyState ────────────────────────────────────────────
function EmptyState({ icon = 'inbox', title, desc, cta, kbd, onAction }) {
  return (
    <div style={{
      textAlign:'center', padding:'48px 24px',
      display:'flex', flexDirection:'column', alignItems:'center', gap:12,
    }}>
      <div style={{
        width:56, height:56, borderRadius:14,
        border:`1px solid ${C.goldBorder}`,
        background: C.card,
        display:'flex', alignItems:'center', justifyContent:'center',
        marginBottom:4,
      }}>
        <i data-lucide={icon} style={{width:22, height:22, color:C.textMuted, opacity:0.6}}/>
      </div>
      {title && (
        <div style={{fontFamily:'Cormorant Garamond,serif', fontStyle:'italic',
          fontSize:22, color:C.text, letterSpacing:'0.02em'}}>{title}</div>
      )}
      {desc && (
        <div style={{fontSize:13, color:C.textMuted,
          maxWidth:320, lineHeight:1.5}}>{desc}</div>
      )}
      {cta && (
        <button onClick={onAction} style={{
          marginTop:10,
          background:'var(--gold-bg)',
          border:`1px solid ${C.goldBorder}`,
          borderRadius:8, padding:'9px 16px',
          fontFamily:'DM Sans,sans-serif', fontSize:13,
          color:C.gold, letterSpacing:'0.06em',
          cursor:'pointer', display:'inline-flex', alignItems:'center', gap:8,
        }}>
          {cta}
          {kbd && (
            <kbd style={{fontFamily:'monospace', fontSize:10,
              background:C.card2 || C.card, border:`1px solid ${C.goldBorder}`,
              borderRadius:4, padding:'1px 6px', color:C.textMuted}}>{kbd}</kbd>
          )}
        </button>
      )}
    </div>
  );
}

// ─── PerfectDayModal ───────────────────────────────────────
function PerfectDayModal({ details, onClose }) {
  return (
    <div style={{
      position:'fixed', inset:0, zIndex:999,
      background:'color-mix(in srgb, var(--bg) 90%, transparent)',
      display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
      padding:24, animation:'euFadeIn 0.6s ease',
    }}>
      <div style={{
        position:'absolute', inset:0,
        background:'radial-gradient(ellipse at center, var(--gold-glow) 0%, transparent 65%)',
        opacity:0.25, animation:'euGoldPulse 2.4s ease-in-out infinite',
        pointerEvents:'none',
      }}/>
      <div style={{fontSize:11, letterSpacing:'0.25em',
        color:'var(--gold)', textTransform:'uppercase', marginBottom:18, opacity:0.75}}>
        ✦ Día Perfecto ✦
      </div>
      <div style={{
        fontFamily:'Cormorant Garamond,serif', fontSize:54, fontWeight:600,
        color:'var(--text)', letterSpacing:'0.06em', textAlign:'center',
        animation:'euLevelUpRise 1.2s ease-out',
      }}>
        Todas las virtudes
      </div>
      <div style={{fontFamily:'Cormorant Garamond,serif', fontStyle:'italic',
        fontSize:18, color:'var(--mid)', marginTop:12, marginBottom:28,
        textAlign:'center', maxWidth:380, lineHeight:1.5}}>
        Cumpliste con cada categoría hoy.
      </div>
      {(details.bonusXp > 0 || details.bonusEc > 0) && (
        <div style={{display:'flex', gap:10, marginBottom:32}}>
          {details.bonusXp > 0 && (
            <div style={{padding:'8px 18px', background:'var(--gold-bg)',
              border:'1px solid var(--gold-border)', borderRadius:100,
              fontSize:13, color:'var(--gold)', letterSpacing:'0.08em'}}>
              +{details.bonusXp} XP bonus
            </div>
          )}
          {details.bonusEc > 0 && (
            <div style={{padding:'8px 18px', background:'var(--gold-bg)',
              border:'1px solid var(--gold-border)', borderRadius:100,
              fontSize:13, color:'var(--gold)', letterSpacing:'0.08em'}}>
              +{details.bonusEc} EC bonus
            </div>
          )}
        </div>
      )}
      <button onClick={onClose} style={{
        background:'transparent', border:'1.5px solid var(--gold-border)',
        borderRadius:10, padding:'12px 32px',
        fontFamily:'DM Sans,sans-serif', fontSize:12, letterSpacing:'0.18em',
        color:'var(--gold)', cursor:'pointer', textTransform:'uppercase',
      }}>Continuar</button>
    </div>
  );
}

// ─── ComboBonusSheet ───────────────────────────────────────
function ComboBonusSheet({ combo, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div style={{
      position:'fixed', inset:0, zIndex:997,
      background:'color-mix(in srgb, var(--bg) 60%, transparent)',
      display:'flex', alignItems:'flex-end', justifyContent:'center',
      animation:'euFadeIn 0.25s ease',
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        background:'linear-gradient(180deg, var(--surf), var(--bg))',
        border:'1px solid var(--gold-border)',
        borderTopLeftRadius:20, borderTopRightRadius:20,
        padding:'24px 22px', width:'100%', maxWidth:420,
        animation:'euAchievementRise 0.4s ease-out',
        boxShadow:'0 -12px 40px color-mix(in srgb, var(--bg) 50%, black)',
      }}>
        {/* Countdown bar */}
        <div style={{
          position:'absolute', top:0, left:0, right:0, height:2,
          background:'var(--gold)', borderRadius:'2px 2px 0 0',
          animation:'undoCountdown 4s linear forwards',
        }}/>
        <div style={{display:'flex', alignItems:'center', gap:14}}>
          <div style={{fontSize:36, lineHeight:1,
            filter:'drop-shadow(0 0 12px var(--gold-glow))'}}>
            {combo.icon || '⚡'}
          </div>
          <div style={{flex:1, minWidth:0}}>
            <div style={{fontSize:10, letterSpacing:'0.2em', color:'var(--gold)',
              opacity:0.7, textTransform:'uppercase', marginBottom:3}}>
              Combo desbloqueado
            </div>
            <div style={{fontFamily:'Cormorant Garamond,serif', fontSize:20,
              fontWeight:600, color:'var(--text)', letterSpacing:'0.03em'}}>
              {combo.name}
            </div>
            {combo.description && (
              <div style={{fontSize:12, color:'var(--mid)', marginTop:2, lineHeight:1.4}}>
                {combo.description}
              </div>
            )}
          </div>
          <div style={{textAlign:'right', flexShrink:0}}>
            {combo.xp > 0 && (
              <div style={{fontSize:14, color:'var(--gold)', fontWeight:600}}>
                +{combo.xp} XP
              </div>
            )}
            {combo.ec > 0 && (
              <div style={{fontSize:11, color:'var(--dim)', marginTop:2}}>
                +{combo.ec} EC
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  GreekColumn, ProgressRing, ModuleCard, HabitRow, QuoteDisplay, BottomNav, LevelUpModal,
  StreakHeatmap, AchievementSheet, EmptyState, Skeleton, PerfectDayModal, ComboBonusSheet,
});
