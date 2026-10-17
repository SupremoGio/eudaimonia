// EUDAIMONIA UX Patches — Celebration, Streak, Empty States, Skeletons

// ═══════════════════════════════════════════════════════════
// LEVEL UP MODAL
// ═══════════════════════════════════════════════════════════
function LevelUpModalPatch() {
  const c = EU_COLORS;

  // Mini columna griega
  const Column = ({ level = 4, size = 96 }) => {
    const h = size * 1.45;
    const cx = size / 2;
    const shaftW = size * 0.26;
    const shaftTop = h * 0.07;
    const shaftBot = h * 0.80;
    const drumH = (shaftBot - shaftTop) / 10;

    return (
      <svg width={size} height={h} viewBox={`0 0 ${size} ${h}`}>
        <defs>
          <linearGradient id="lvg1" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#7A5520"/>
            <stop offset="50%" stopColor="#C9A84C"/>
            <stop offset="100%" stopColor="#F0D880"/>
          </linearGradient>
        </defs>
        {Array.from({length: 10}).map((_, i) => {
          const fromBottom = 9 - i;
          const filled = fromBottom < level;
          const entasis = 1 + Math.sin(Math.PI * ((fromBottom + 0.5) / 10)) * 0.14;
          const w = shaftW * entasis;
          const y = shaftTop + i * drumH;
          return (
            <rect key={i}
              x={cx - w/2} y={y + 0.5} width={w} height={drumH - 1} rx={0.8}
              fill={filled ? 'url(#lvg1)' : '#1E1B2A'}
              stroke={filled ? 'rgba(201,168,76,0.5)' : 'rgba(201,168,76,0.08)'}
              strokeWidth={0.5}
            />
          );
        })}
        {/* Capital */}
        <rect x={cx - size*0.21} y={shaftTop - h*0.045}
          width={size*0.42} height={h*0.045} rx={1}
          fill="url(#lvg1)"/>
        {/* Base */}
        <rect x={cx - shaftW*0.65} y={shaftBot} width={shaftW*1.3} height={h*0.03}
          fill="#1E1B2A" stroke="rgba(201,168,76,0.14)" strokeWidth={0.5}/>
        <rect x={cx - size*0.25} y={shaftBot + h*0.031} width={size*0.5} height={h*0.038}
          fill="#1A1726" stroke="rgba(201,168,76,0.1)" strokeWidth={0.5}/>
      </svg>
    );
  };

  return (
    <Frame pad={20}>
      <Eyebrow>PATCH #14 · CELEBRACIÓN</Eyebrow>
      <SectionTitle>Modal de subida de nivel</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 16, lineHeight:1.5 }}>
        Reemplazo del toast genérico cuando el backend devuelve <code>level_up: true</code>.
      </div>

      <div style={{
        background:'rgba(9,7,15,0.95)',
        border:`1px solid ${c.border2}`, borderRadius: 14,
        padding:'36px 24px',
        textAlign:'center', position:'relative', overflow:'hidden',
      }}>
        {/* Radial glow */}
        <div style={{
          position:'absolute', inset: 0,
          background:`radial-gradient(ellipse at center, rgba(201,168,76,0.12), transparent 65%)`,
          pointerEvents:'none',
        }}/>
        <div style={{ position:'relative' }}>
          <div style={{
            fontSize: 11, letterSpacing:'0.28em', color: c.gold,
            textTransform:'uppercase', marginBottom: 16, opacity:0.75,
          }}>¡SUBISTE DE NIVEL!</div>

          <div style={{ display:'flex', justifyContent:'center', marginBottom: 18 }}>
            <Column level={4} size={84}/>
          </div>

          <div style={{ fontSize: 11, letterSpacing:'0.22em', color: c.gold,
            marginBottom: 4, opacity: 0.65 }}>NIVEL 4</div>
          <div style={{ fontFamily: c.serif, fontSize: 40, fontWeight: 600,
            color: c.text, letterSpacing:'0.06em' }}>
            ESTRATEGOS
          </div>
          <div style={{ fontFamily: c.serif, fontStyle:'italic', fontSize: 16,
            color: c.mid, marginTop: 4, marginBottom: 26 }}>
            El estratega
          </div>

          <div style={{
            display:'inline-block', padding:'12px 28px',
            background:'transparent', border:`1.5px solid rgba(201,168,76,0.4)`,
            borderRadius: 10,
            fontSize: 12, letterSpacing:'0.15em',
            color: c.gold, cursor:'pointer', textTransform:'uppercase',
          }}>CONTINUAR</div>
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// STREAK HEATMAP
// ═══════════════════════════════════════════════════════════
function StreakHeatmapPatch() {
  const c = EU_COLORS;
  // 21 días: [(intensity 0-1), ...] — sample data
  const days = [
    0.8, 0.6, 0.4, 0,   0.7, 1.0, 0.9,
    0.5, 0.8, 0.7, 0.3, 0.9, 1.0, 0.6,
    0.7, 0.8, 0.5, 0.9, 1.0, 0.8, 0.7,
  ];
  const months = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];

  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #15 · RACHA</Eyebrow>
      <SectionTitle>Heatmap de últimos 21 días</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        Reemplaza el "12 días consecutivos" con un GitHub-style heatmap.
        Intensidad oro = XP del día.
      </div>

      <div style={{
        background: c.card, border:`1px solid ${c.border}`,
        borderRadius: 14, padding: 18,
      }}>
        <div style={{ display:'flex', justifyContent:'space-between',
          alignItems:'flex-end', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize:11, letterSpacing:'0.15em',
              color: c.textNew, textTransform:'uppercase', marginBottom: 4 }}>
              Racha actual
            </div>
            <div style={{ display:'flex', alignItems:'baseline', gap: 6 }}>
              <span style={{ fontFamily: c.serif, fontSize: 42, fontWeight: 600,
                color: c.gold, lineHeight: 1 }}>12</span>
              <span style={{ fontSize: 13, color: c.textNew }}>días</span>
            </div>
          </div>
          <div style={{
            fontSize: 11, padding:'4px 10px',
            background: c.goldBg, border:`1px solid ${c.border2}`,
            borderRadius: 100, color: c.gold,
            letterSpacing:'0.08em',
          }}>✦ +5% XP activo</div>
        </div>

        {/* Heatmap grid 3 weeks × 7 days */}
        <div style={{
          display:'grid', gridTemplateColumns:'auto repeat(7, 1fr)',
          gap: 4, marginBottom: 14,
        }}>
          <div/>
          {months.map(m => (
            <div key={m} style={{
              fontSize: 10, color: c.textNew, textAlign:'center',
              letterSpacing:'0.06em',
            }}>{m}</div>
          ))}
          {[0,1,2].map(week => (
            <React.Fragment key={week}>
              <div style={{ fontSize: 10, color: c.textNew, alignSelf:'center' }}>
                {week === 0 ? 'Hace 3' : week === 1 ? 'Hace 2' : 'Esta'}
              </div>
              {days.slice(week*7, week*7+7).map((d, di) => (
                <div key={di} style={{
                  aspectRatio: '1/1', borderRadius: 4,
                  background: d === 0
                    ? 'rgba(201,168,76,0.04)'
                    : `oklch(${20 + d * 50}% ${0.04 + d * 0.16} 80)`,
                  border: d > 0 ? `1px solid oklch(${30+d*30}% ${0.05+d*0.1} 80)` : `1px dashed ${c.border}`,
                  boxShadow: d >= 0.9 ? `0 0 8px oklch(65% 0.18 80 / 0.4)` : 'none',
                }}/>
              ))}
            </React.Fragment>
          ))}
        </div>

        {/* Legend */}
        <div style={{ display:'flex', alignItems:'center', gap: 8,
          fontSize: 11, color: c.textNew }}>
          <span>Menos</span>
          {[0.1, 0.3, 0.5, 0.7, 1.0].map(v => (
            <div key={v} style={{
              width: 14, height: 14, borderRadius: 3,
              background: `oklch(${20 + v * 50}% ${0.04 + v * 0.16} 80)`,
              border: `1px solid oklch(${30+v*30}% ${0.05+v*0.1} 80)`,
            }}/>
          ))}
          <span>Más</span>

          <div style={{ flex: 1 }}/>
          <div style={{ display:'flex', gap: 6 }}>
            {[7, 21, 30].map(m => (
              <div key={m} style={{
                fontSize: 10, padding:'2px 8px', borderRadius: 100,
                background: 12 >= m ? c.goldBg : c.card2,
                border: `1px solid ${12 >= m ? c.border2 : c.border}`,
                color: 12 >= m ? c.gold : c.textNew,
                letterSpacing:'0.08em',
              }}>{m}d{12 >= m ? ' ✓' : ''}</div>
            ))}
          </div>
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// CLASSIFICATION CARD — Diamond celebration
// ═══════════════════════════════════════════════════════════
function ClassificationPatch() {
  const c = EU_COLORS;

  const TIERS = [
    { id:'carbon',   icon:'🪨', label:'Carbón',  desc:'<7 XP o sin progreso', col:'#475569' },
    { id:'iron',     icon:'⚔️', label:'Hierro',  desc:'8-15 XP · ≥2 categorías', col:'#94a3b8' },
    { id:'gold',     icon:'🥇', label:'Oro',     desc:'16+ XP · ≥3 categorías', col:'#fbbf24' },
    { id:'diamond',  icon:'💎', label:'Diamante',desc:'20+ XP · ≥1 alto impacto', col:'#7dd3fc' },
  ];

  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #16 · CLASIFICACIÓN</Eyebrow>
      <SectionTitle>Escala progresiva visible</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        Mostrar la escala completa (Carbón → Diamante) con el tier actual destacado.
        Hoy solo se ve el tier ganado.
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr', gap: 8 }}>
        {TIERS.map((t, i) => {
          const isCurrent = t.id === 'iron'; // estás en hierro
          const isPast = i < 1;
          return (
            <div key={t.id} style={{
              background: isCurrent ? `${t.col}15` : c.card,
              border: `1px solid ${isCurrent ? t.col + '88' : c.border}`,
              borderRadius: 12, padding: '12px 10px',
              textAlign:'center', position:'relative',
              opacity: !isCurrent && !isPast ? 0.5 : 1,
              boxShadow: isCurrent ? `0 0 18px ${t.col}33` : 'none',
            }}>
              {isCurrent && (
                <div style={{
                  position:'absolute', top: -8, left: '50%',
                  transform:'translateX(-50%)',
                  background: t.col, color: '#0a0a1a',
                  padding:'2px 8px', borderRadius: 100,
                  fontSize: 9, letterSpacing:'0.1em', fontWeight: 600,
                }}>ACTUAL</div>
              )}
              <div style={{ fontSize: 28, marginBottom: 4 }}>{t.icon}</div>
              <div style={{
                fontFamily: c.serif, fontSize: 18, fontWeight: 600,
                color: isCurrent ? t.col : (isPast ? c.text : c.mid),
              }}>{t.label}</div>
              <div style={{
                fontSize: 10, color: c.textNew, marginTop: 4, lineHeight: 1.4,
              }}>{t.desc}</div>
            </div>
          );
        })}
      </div>

      {/* Progress to next */}
      <div style={{
        marginTop: 16, padding:'14px 16px',
        background: c.card, border:`1px solid ${c.border}`,
        borderRadius: 12,
      }}>
        <div style={{ display:'flex', justifyContent:'space-between', marginBottom: 8 }}>
          <span style={{ fontSize: 12, color: c.textNew }}>
            Llevas <strong style={{color:c.text}}>12 XP</strong> · faltan 4 para Oro
          </span>
          <span style={{ fontSize: 11, color: c.warning }}>
            🥇 +1 categoría requerida
          </span>
        </div>
        <div style={{ height: 4, background:'rgba(201,168,76,0.06)',
          borderRadius: 2, overflow:'hidden' }}>
          <div style={{ width:'75%', height:'100%',
            background:`linear-gradient(90deg, ${c.gold}, #fbbf24)`,
            boxShadow:`0 0 6px ${c.gold}66` }}/>
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// EMPTY STATE
// ═══════════════════════════════════════════════════════════
function EmptyStatePatch() {
  const c = EU_COLORS;
  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #17 · ESTADOS</Eyebrow>
      <SectionTitle>Empty states con dirección</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        En lugar de "Sin next actions — captura algo", dar una <strong>siguiente acción concreta</strong>.
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 14 }}>
        {/* ANTES */}
        <div style={{
          background: c.card, border:`1px solid ${c.danger}33`,
          borderRadius: 12, padding: 36, textAlign:'center',
        }}>
          <div style={{ fontSize:11, color:c.danger, marginBottom: 14,
            letterSpacing:'0.12em' }}>✗ ANTES</div>
          <div style={{ fontSize: 22, opacity: 0.22, marginBottom: 12 }}>⚡</div>
          <div style={{ fontSize: 11, color: c.textOld,
            letterSpacing:'0.1em' }}>SIN NEXT ACTIONS</div>
        </div>

        {/* DESPUÉS */}
        <div style={{
          background: c.card, border:`1px solid ${c.border2}`,
          borderRadius: 12, padding: 28, textAlign:'center',
        }}>
          <div style={{ fontSize:11, color:c.success, marginBottom: 14,
            letterSpacing:'0.12em' }}>✓ DESPUÉS</div>
          <div style={{
            width: 48, height: 48, borderRadius: 14,
            background: c.goldBg, border:`1px solid ${c.border2}`,
            display:'flex', alignItems:'center', justifyContent:'center',
            margin:'0 auto 14px', fontSize: 22, color: c.gold,
          }}>✓</div>
          <div style={{ fontFamily: c.serif, fontStyle:'italic',
            fontSize: 18, color: c.text, marginBottom: 6 }}>
            Inbox limpio.
          </div>
          <div style={{ fontSize: 13, color: c.textNew, lineHeight: 1.5,
            marginBottom: 16 }}>
            No tienes pendientes. ¿Capturas algo para no perderlo?
          </div>
          <div style={{
            display:'inline-block', padding:'8px 16px',
            background: c.gold, color: c.bg, borderRadius: 8,
            fontSize: 12, fontWeight: 600, letterSpacing:'0.08em',
            cursor: 'pointer',
          }}>+ Capturar idea (c)</div>
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// SKELETON LOADER
// ═══════════════════════════════════════════════════════════
function SkeletonPatch() {
  const c = EU_COLORS;
  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #18 · LOADING</Eyebrow>
      <SectionTitle>Skeleton con shimmer</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        Hoy hay flash de blanco al hacer fetch. Usa el keyframe <code>euShimmer</code>
        que ya existe en <code>base_eudaimonia.html</code>.
      </div>

      <style>{`
        @keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
        .sk {
          background: linear-gradient(90deg,
            rgba(201,168,76,0.04) 0%,
            rgba(201,168,76,0.12) 50%,
            rgba(201,168,76,0.04) 100%);
          background-size: 200% 100%;
          animation: shimmer 1.6s linear infinite;
        }
      `}</style>

      {[1, 2, 3].map(i => (
        <div key={i} style={{
          background: c.card, border: `1px solid ${c.border}`,
          borderRadius: 10, padding: '14px 16px', marginBottom: 8,
          display:'flex', alignItems:'center', gap: 12,
        }}>
          <div className="sk" style={{ width: 22, height: 22, borderRadius: 6 }}/>
          <div style={{ flex: 1 }}>
            <div className="sk" style={{
              height: 13, width: `${60 + i * 8}%`, borderRadius: 4, marginBottom: 6,
            }}/>
            <div className="sk" style={{
              height: 10, width: `${30 + i * 5}%`, borderRadius: 4,
            }}/>
          </div>
          <div className="sk" style={{ width: 40, height: 18, borderRadius: 100 }}/>
        </div>
      ))}
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// DANGER ZONE — Move out of Acta Diurna
// ═══════════════════════════════════════════════════════════
function DangerZonePatch() {
  const c = EU_COLORS;

  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #19 · ZONA PELIGRO</Eyebrow>
      <SectionTitle>Reset fuera de Acta Diurna</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        Actualmente "Reset Gamificación" está al lado del Pipeline en /actividades.
        Foot-gun gigante. Va en <code>/perfil → Zona de peligro</code>.
      </div>

      {/* Mock perfil section */}
      <div style={{
        background: c.card, border:`1px solid ${c.border}`,
        borderRadius: 14, padding: 20, marginBottom: 12,
      }}>
        <div style={{ fontSize: 11, letterSpacing:'0.15em',
          color: c.textNew, textTransform:'uppercase', marginBottom: 12 }}>
          Configuración · Perfil
        </div>
        {[
          { l:'Datos personales',    s:'Nombre, foto, contacto' },
          { l:'Medidas corporales',  s:'Peso, altura, objetivos' },
          { l:'Notificaciones',      s:'Email, recordatorios' },
          { l:'Exportar datos',      s:'JSON / CSV completos' },
        ].map(o => (
          <div key={o.l} style={{
            padding:'12px 0', borderTop: `1px solid ${c.border}`,
            display:'flex', justifyContent:'space-between', alignItems:'center',
          }}>
            <div>
              <div style={{ fontSize: 14, color: c.text }}>{o.l}</div>
              <div style={{ fontSize: 11, color: c.textNew, marginTop: 1 }}>{o.s}</div>
            </div>
            <div style={{ color: c.textNew, fontSize: 18 }}>→</div>
          </div>
        ))}
      </div>

      {/* Danger zone separado */}
      <div style={{
        background:'rgba(244,63,94,0.05)',
        border:`1px solid ${c.danger}33`, borderRadius: 14, padding: 20,
      }}>
        <div style={{
          fontSize: 11, letterSpacing:'0.15em',
          color: c.danger, textTransform:'uppercase', marginBottom: 6, fontWeight: 600,
        }}>⚠ Zona de peligro</div>
        <div style={{ fontSize: 14, color: c.text, marginBottom: 4 }}>
          Reset de Gamificación
        </div>
        <div style={{ fontSize: 12, color: c.textNew, lineHeight: 1.55, marginBottom: 14 }}>
          Borra todo XP, EC, racha, logros y badges. Los rewards de la tienda se conservan.
          Esta acción es irreversible.
        </div>
        <div style={{
          display:'inline-block', padding:'10px 16px',
          background:'rgba(244,63,94,0.1)',
          border:`1px solid ${c.danger}55`, borderRadius: 8,
          fontSize: 12, letterSpacing:'0.1em', color: c.danger,
          textTransform:'uppercase', cursor:'pointer',
        }}>Resetear gamificación</div>
      </div>
    </Frame>
  );
}

Object.assign(window, {
  LevelUpModalPatch, StreakHeatmapPatch, ClassificationPatch,
  EmptyStatePatch, SkeletonPatch, DangerZonePatch,
});
