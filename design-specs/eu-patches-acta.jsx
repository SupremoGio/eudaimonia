// EUDAIMONIA UX Patches — Acta Diurna refactor
// Hero unificado · activity buttons · undo toast · categorías

// ═══════════════════════════════════════════════════════════
// ACTA DIURNA HERO — ANTES
// ═══════════════════════════════════════════════════════════
function ActaHeroBefore() {
  const c = EU_COLORS;
  const Stat = ({ l, v, sub, color = c.gold }) => (
    <div style={{
      background: c.card, border: `1px solid ${c.border}`,
      borderRadius: 14, padding:'14px 16px',
      position:'relative', overflow:'hidden',
    }}>
      <div style={{ position:'absolute', top:0, left:0, right:0, height:3,
        background:color, borderRadius:'14px 14px 0 0' }}/>
      <div style={{ fontSize: '.44rem', color: c.textOld,
        letterSpacing:'.18em', textTransform:'uppercase', marginBottom: 6 }}>{l}</div>
      <div style={{ fontFamily:c.serif, fontSize:'2rem', fontStyle:'italic',
        color, lineHeight:1 }}>{v}</div>
      <div style={{ fontSize:'.48rem', color:c.textOld, marginTop: 3 }}>{sub}</div>
    </div>
  );

  return (
    <Frame pad={20}>
      <div style={{
        padding:'6px 10px', background:c.danger+'22',
        border:`1px solid ${c.danger}55`,
        borderRadius: 6, display:'inline-block',
        fontSize:11, color:c.danger, letterSpacing:'0.12em',
        marginBottom: 16,
      }}>✗ ANTES — 5 stat cards + clasificación + nivel</div>

      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:10, marginBottom:16 }}>
        <Stat l="XP HOY"      v="12"  sub="meta 15+" color="#a78bfa"/>
        <Stat l="XP SEMANA"   v="78"  sub="meta 100+" color="#06b6d4"/>
        <Stat l="XP MES"      v="312" sub="meta 450+" color="#10b981"/>
        <Stat l="EUDA-CREDITS" v="48"  sub="ver tienda →" color="#f59e0b"/>
        <Stat l="RACHA"       v="12"  sub="✦ +5% XP activo" color="#ec4899"/>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
        <div style={{
          background:'#f59e0b22', border:'1px solid #f59e0b66',
          borderRadius:14, padding:'14px 16px', display:'flex', alignItems:'center', gap:12,
        }}>
          <div style={{ fontSize: 28 }}>⚔️</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize:'.44rem', color:c.textOld,
              letterSpacing:'.16em', textTransform:'uppercase' }}>Clasificación de hoy</div>
            <div style={{ fontFamily:c.serif, fontSize:'1.2rem', fontStyle:'italic',
              color:'#f59e0b' }}>Hierro</div>
            <div style={{ fontSize:'.48rem', color:c.textOld,
              letterSpacing:'.1em', textTransform:'uppercase', marginTop: 2 }}>
              8-15 XP · ≥2 categorías
            </div>
          </div>
          <div style={{ fontFamily:c.serif, fontStyle:'italic', fontSize:'1.4rem',
            color:'#f59e0b' }}>12</div>
        </div>

        <div style={{
          background:c.card, border:`1px solid ${c.border}`,
          borderRadius:14, padding:'14px 16px',
        }}>
          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
            <div>
              <div style={{ fontSize:'.44rem', color:c.textOld,
                letterSpacing:'.16em', textTransform:'uppercase' }}>Nivel 3</div>
              <div style={{ fontFamily:c.serif, fontSize:'1rem', fontStyle:'italic',
                color:'#a78bfa' }}>ASQUETÉS</div>
            </div>
            <div style={{ textAlign:'right' }}>
              <div style={{ fontSize:'.48rem', color:c.textOld }}>Total XP</div>
              <div style={{ fontFamily:c.serif, fontStyle:'italic', fontSize:'1rem',
                color:'#a78bfa' }}>1,750</div>
            </div>
          </div>
          <div style={{ fontSize:'.48rem', color:c.textOld, marginBottom:6 }}>
            El practicante
          </div>
          <div style={{ height:5, background:c.card2, borderRadius:100, overflow:'hidden' }}>
            <div style={{ width:'70%', height:'100%',
              background:'linear-gradient(90deg,#7A5520,#C9A84C)' }}/>
          </div>
          <div style={{ fontSize:'.46rem', color:c.textOld, marginTop: 5 }}>
            250 XP para siguiente nivel
          </div>
        </div>
      </div>

      <div style={{
        marginTop: 16, padding:'10px 12px',
        background:'rgba(244,63,94,0.07)',
        border:`1px solid ${c.danger}44`, borderRadius: 8,
        fontSize: 12, color: c.danger, lineHeight: 1.5,
      }}>
        <strong>Problemas:</strong> 7 elementos numéricos antes del primer botón de actividad ·
        labels de 6.7px ilegibles · "RACHA" duplicada · clasificación + nivel sin jerarquía clara.
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// ACTA DIURNA HERO — DESPUÉS
// ═══════════════════════════════════════════════════════════
function ActaHeroAfter() {
  const c = EU_COLORS;
  const xpToday = 12, xpGoal = 15;
  const pct = Math.min(1, xpToday / xpGoal);

  return (
    <Frame pad={20}>
      <div style={{
        padding:'6px 10px', background:c.success+'22',
        border:`1px solid ${c.success}55`,
        borderRadius: 6, display:'inline-block',
        fontSize:11, color:c.success, letterSpacing:'0.12em',
        marginBottom: 16,
      }}>✓ DESPUÉS — un solo hero, foco en "hoy"</div>

      {/* Hero unificado */}
      <div style={{
        background:'linear-gradient(140deg,#1C1830,#110F20)',
        border:`1px solid ${c.border2}`,
        borderRadius: 18, padding: '22px 22px 20px',
        position:'relative', overflow:'hidden',
        boxShadow:'0 10px 36px rgba(0,0,0,0.4)',
      }}>
        <div style={{
          fontSize:11, letterSpacing:'0.2em', color:c.gold,
          textTransform:'uppercase', opacity: 0.7, marginBottom: 6,
        }}>Martes 19 de mayo · Nivel 3 · ASQUETÉS</div>

        <div style={{ display:'flex', alignItems:'baseline', gap: 14, marginBottom: 14 }}>
          <div style={{
            fontFamily: c.serif, fontSize: 64, fontWeight: 600,
            color: c.goldL, lineHeight: 1, letterSpacing:'0.02em',
            textShadow:'0 0 24px rgba(201,168,76,0.35)',
          }}>{xpToday}</div>
          <div style={{
            fontSize: 18, color: c.mid, fontFamily: c.sans,
          }}>XP <span style={{color:c.textNew}}>/ {xpGoal} meta</span></div>
        </div>

        {/* Barra de progreso día */}
        <div style={{ height: 6, background:'rgba(201,168,76,0.08)',
          borderRadius:3, overflow:'hidden', marginBottom: 8 }}>
          <div style={{
            height:'100%', width:`${pct*100}%`,
            background:'linear-gradient(90deg,#7A5520,#C9A84C,#E8C96D)',
            boxShadow:'0 0 12px rgba(201,168,76,0.6)',
          }}/>
        </div>

        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <div style={{ display:'flex', gap: 14, alignItems:'center' }}>
            <span style={{
              fontSize: 12, color: '#fbbf24',
              background:'rgba(245,158,11,0.1)',
              border:'1px solid rgba(245,158,11,0.25)',
              padding:'3px 10px', borderRadius: 100,
              letterSpacing:'0.06em',
            }}>⚔️ Hierro</span>
            <span style={{ fontSize: 13, color: c.textNew }}>3 categorías</span>
            <span style={{ fontSize: 13, color: c.textNew }}>·</span>
            <span style={{ fontSize: 13, color: c.gold }}>🔥 12 días</span>
          </div>
          <div style={{ fontSize: 13, color: c.textNew }}>
            250 XP → <span style={{color:c.gold}}>ESTRATEGOS</span>
          </div>
        </div>
      </div>

      {/* Métricas secundarias colapsadas en una sola fila pequeña */}
      <div style={{
        marginTop: 12, padding:'10px 16px',
        background: c.card, border:`1px solid ${c.border}`,
        borderRadius: 12, display:'flex', justifyContent:'space-between',
      }}>
        {[
          {l:'Semana', v:'78',  sub:'/ 100'},
          {l:'Mes',    v:'312', sub:'/ 450'},
          {l:'EC',     v:'48',  sub:'tienda →'},
          {l:'Racha',  v:'12d', sub:'+5% XP'},
        ].map(s => (
          <div key={s.l} style={{ textAlign:'center' }}>
            <div style={{ fontSize:11, color:c.textNew,
              letterSpacing:'0.1em', textTransform:'uppercase' }}>{s.l}</div>
            <div style={{ fontSize:18, fontFamily:c.serif, color:c.text, marginTop: 2 }}>{s.v}</div>
            <div style={{ fontSize:10, color:c.textNew, marginTop:1 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 14, padding:'10px 12px',
        background:'rgba(16,185,129,0.07)',
        border:`1px solid ${c.success}44`, borderRadius: 8,
        fontSize: 12, color: c.success, lineHeight: 1.5,
      }}>
        <strong>Mejoras:</strong> un solo número que importa (XP del día) ·
        progreso visual hacia la meta · clasificación como chip ·
        nivel y siguiente integrados sin card aparte.
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// ACTIVITY BUTTON — ANTES / DESPUÉS
// ═══════════════════════════════════════════════════════════
function ActivityButtonPatch() {
  const c = EU_COLORS;

  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #6 · BOTÓN ACTIVIDAD</Eyebrow>
      <SectionTitle>Botón con jerarquía</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        Stack vertical da más jerarquía y target tap más grande.
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 14 }}>
        {/* ANTES */}
        <div>
          <div style={{ fontSize:11, color:c.danger, marginBottom: 10,
            letterSpacing:'0.12em' }}>✗ ANTES</div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr', gap: 6 }}>
            {[
              { l:'Meditar',          xp:'+2', tier:'micro' },
              { l:'Ejercicio Gym',    xp:'+4 · 1EC', tier:'progreso', done:true },
              { l:'Resolver 5 problemas reales', xp:'+6 · 2EC', tier:'alto' },
            ].map((a,i) => (
              <div key={i} style={{
                background: a.done ? 'rgba(124,58,237,.08)' : c.card2,
                border:`1px solid ${a.done ? 'rgba(124,58,237,.3)' : c.border}`,
                color: a.done ? c.text : c.mid,
                padding:'10px 12px', borderRadius:10,
                display:'flex', justifyContent:'space-between', alignItems:'center',
                fontSize:'.6rem', minHeight: 44, gap:6,
              }}>
                <span>{a.l}</span>
                <span style={{
                  fontSize:'.44rem', padding:'2px 6px', borderRadius:100,
                  background: a.tier==='alto' ? 'rgba(245,158,11,.12)'
                    : a.tier==='progreso' ? 'rgba(16,185,129,.12)' : c.border,
                  color: a.tier==='alto' ? c.warning : a.tier==='progreso' ? c.success : c.textOld,
                  border: `1px solid ${
                    a.tier==='alto' ? 'rgba(245,158,11,.3)'
                      : a.tier==='progreso' ? 'rgba(16,185,129,.25)' : 'transparent'}`,
                  whiteSpace:'nowrap',
                }}>{a.xp}</span>
              </div>
            ))}
          </div>
        </div>

        {/* DESPUÉS */}
        <div>
          <div style={{ fontSize:11, color:c.success, marginBottom: 10,
            letterSpacing:'0.12em' }}>✓ DESPUÉS</div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr', gap: 8 }}>
            {[
              { l:'Meditar',          xp:2, ec:0, tier:'micro',    cat:'Salud',     hue:45,  done:false },
              { l:'Ejercicio Gym',    xp:4, ec:1, tier:'progreso', cat:'Salud',     hue:45,  done:true  },
              { l:'Resolver 5 problemas reales', xp:6, ec:2, tier:'alto', cat:'Programación', hue:120, done:false },
            ].map((a,i) => {
              const acc = `oklch(65% 0.15 ${a.hue})`;
              const accBg = `oklch(20% 0.05 ${a.hue})`;
              return (
                <div key={i} style={{
                  background: a.done ? accBg : c.card,
                  border:`1px solid ${a.done ? acc+'66' : c.border}`,
                  borderRadius:10, padding:'12px 14px',
                  position:'relative', overflow:'hidden',
                  boxShadow: a.done ? `0 0 0 transparent, 0 0 16px ${accBg}` : 'none',
                }}>
                  {a.tier === 'alto' && (
                    <div style={{
                      position:'absolute', top:0, right:0,
                      padding:'2px 8px',
                      background:'rgba(245,158,11,0.18)',
                      color: c.warning, fontSize: 9,
                      letterSpacing:'0.15em', borderBottomLeftRadius: 6,
                    }}>ALTO IMPACTO</div>
                  )}
                  <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
                    <div style={{
                      width: 22, height: 22, borderRadius: 6, flexShrink: 0,
                      background: a.done ? acc : 'transparent',
                      border: `1.5px solid ${a.done ? acc : c.border2}`,
                      display:'flex', alignItems:'center', justifyContent:'center',
                    }}>
                      {a.done && <span style={{color:c.bg, fontSize:11, fontWeight:700}}>✓</span>}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 14, color: c.text,
                        textDecoration: a.done ? 'line-through' : 'none',
                        opacity: a.done ? 0.7 : 1,
                      }}>{a.l}</div>
                      <div style={{ fontSize: 11, color: c.textNew, marginTop: 2 }}>
                        <span style={{color:acc}}>{a.cat}</span> · {a.tier}
                      </div>
                    </div>
                    <div style={{ textAlign:'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 14, color: c.gold, fontWeight: 600 }}>+{a.xp} XP</div>
                      {a.ec > 0 && (
                        <div style={{ fontSize: 11, color: c.textNew, marginTop: 1 }}>
                          +{a.ec} EC
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// UNDO TOAST
// ═══════════════════════════════════════════════════════════
function UndoToastPatch() {
  const c = EU_COLORS;
  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #7 · UNDO</Eyebrow>
      <SectionTitle>Toast con deshacer (5s)</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        Cada <code>logAct(key)</code> debe poder revertirse 5s. El backend tiene la lógica;
        falta exponer un <code>/api/log/undo/{'<id>'}</code>.
      </div>

      {/* Pantalla mock con toast */}
      <div style={{
        background: c.bg, border: `1px solid ${c.border}`,
        borderRadius: 12, padding: 18, position:'relative', minHeight: 280,
      }}>
        <div style={{
          padding:'10px 14px',
          background: 'oklch(20% 0.05 45)',
          border: '1px solid oklch(35% 0.09 45)',
          borderRadius: 10, marginBottom: 8,
          display:'flex', justifyContent:'space-between', alignItems:'center',
        }}>
          <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
            <div style={{ width:22, height:22, borderRadius:6,
              background:'oklch(65% 0.15 45)',
              display:'flex', alignItems:'center', justifyContent:'center' }}>
              <span style={{color:c.bg, fontSize:11, fontWeight:700}}>✓</span>
            </div>
            <span style={{ fontSize:14, color:c.text, textDecoration:'line-through', opacity:0.7 }}>
              Meditar
            </span>
          </div>
          <span style={{ fontSize:13, color:c.gold }}>+2 XP</span>
        </div>

        <div style={{ padding:'10px 14px', background:c.card, border:`1px solid ${c.border}`,
          borderRadius:10, marginBottom: 8, color: c.textNew, fontSize:14 }}>
          Ejercicio Gym <span style={{float:'right', color:c.textNew}}>+4 XP · 1 EC</span>
        </div>
        <div style={{ padding:'10px 14px', background:c.card, border:`1px solid ${c.border}`,
          borderRadius:10, color: c.textNew, fontSize:14 }}>
          Resolver 5 problemas <span style={{float:'right', color:c.textNew}}>+6 XP · 2 EC</span>
        </div>

        {/* TOAST */}
        <div style={{
          position:'absolute', bottom: 18, left: 18, right: 18,
          background: '#1A1627', border:`1px solid ${c.gold}66`,
          borderRadius: 12, padding: '14px 16px',
          display:'flex', alignItems:'center', gap: 12,
          boxShadow:'0 12px 36px rgba(0,0,0,0.5)',
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, color: c.text }}>
              ✓ <strong>Meditar</strong> · +2 XP registrado
            </div>
            <div style={{ fontSize: 11, color: c.textNew, marginTop: 3 }}>
              Total hoy: 12 XP · ⚔️ Hierro
            </div>
          </div>
          <button style={{
            background:'transparent', border:`1px solid ${c.gold}55`,
            color: c.gold, padding:'6px 14px', borderRadius: 7,
            fontSize: 12, letterSpacing:'0.1em', cursor:'pointer',
            fontFamily: c.sans,
          }}>Deshacer (4s)</button>
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// CATEGORY BLOCK — NEW VISUAL
// ═══════════════════════════════════════════════════════════
function CategoryBlockPatch() {
  const c = EU_COLORS;
  const hue = 45; // Hegemonikon
  const acc = `oklch(65% 0.15 ${hue})`;
  const accBg = `oklch(18% 0.04 ${hue})`;
  const accBorder = `oklch(35% 0.09 ${hue})`;

  const acts = [
    { l:'Meditar',           xp:2, ec:0, tier:'micro',    done:true },
    { l:'Ejercicio Gym',     xp:4, ec:1, tier:'progreso', done:true },
    { l:'Pliometría',        xp:3, ec:1, tier:'progreso', done:false },
    { l:'Partido',           xp:3, ec:1, tier:'progreso', done:false },
    { l:'Colación saludable',xp:1, ec:0, tier:'micro',    done:false },
    { l:'Dormir 8 horas',    xp:2, ec:0, tier:'micro',    done:false },
  ];
  const doneCnt = acts.filter(a => a.done).length;

  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #8 · BLOQUE CATEGORÍA</Eyebrow>
      <SectionTitle>Categoría con progreso visible</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        Header con conteo · barra de progreso · botones grid 2 columnas mobile-first.
      </div>

      <div style={{
        background: c.card, border: `1px solid ${c.border}`,
        borderRadius: 14, padding: 18,
      }}>
        {/* Header */}
        <div style={{ display:'flex', alignItems:'center',
          justifyContent:'space-between', marginBottom: 14 }}>
          <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
            <div style={{
              width: 8, height: 8, borderRadius:'50%', background: acc,
              boxShadow: `0 0 8px ${acc}`,
            }}/>
            <div>
              <div style={{
                fontSize:13, fontWeight:600, color:acc, letterSpacing:'0.1em',
              }}>HEGEMONIKON</div>
              <div style={{ fontSize:11, color: c.textNew, marginTop: 1 }}>
                Salud · Mental · Física · Base
              </div>
            </div>
          </div>
          <div style={{
            fontSize:13, color: doneCnt === acts.length ? c.success : acc,
            fontFamily: c.serif,
          }}>{doneCnt} <span style={{color:c.textNew, fontSize:11}}>de {acts.length}</span></div>
        </div>

        {/* Progress bar */}
        <div style={{ height: 3, background:'rgba(201,168,76,0.06)',
          borderRadius: 2, overflow:'hidden', marginBottom: 14 }}>
          <div style={{ height:'100%', width:`${(doneCnt/acts.length)*100}%`,
            background: acc, boxShadow: `0 0 6px ${acc}66` }}/>
        </div>

        {/* Grid */}
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 8 }}>
          {acts.map((a,i) => (
            <div key={i} style={{
              background: a.done ? accBg : 'transparent',
              border: `1px solid ${a.done ? accBorder : c.border}`,
              borderRadius: 9, padding:'10px 12px',
              display:'flex', justifyContent:'space-between', alignItems:'center',
              cursor:'pointer', minHeight: 48,
              transition:'all 0.15s',
            }}>
              <div style={{ display:'flex', alignItems:'center', gap: 9, flex: 1 }}>
                <div style={{
                  width: 18, height: 18, borderRadius: 5, flexShrink: 0,
                  background: a.done ? acc : 'transparent',
                  border: `1.5px solid ${a.done ? acc : c.border2}`,
                  display:'flex', alignItems:'center', justifyContent:'center',
                }}>
                  {a.done && <span style={{color:c.bg, fontSize:10, fontWeight:700}}>✓</span>}
                </div>
                <span style={{
                  fontSize: 13, color: c.text,
                  textDecoration: a.done ? 'line-through' : 'none',
                  opacity: a.done ? 0.65 : 1,
                }}>{a.l}</span>
              </div>
              <span style={{
                fontSize: 11, color: a.tier === 'alto' ? c.warning : c.gold,
                fontWeight: 500,
              }}>+{a.xp}</span>
            </div>
          ))}
        </div>
      </div>
    </Frame>
  );
}

Object.assign(window, {
  ActaHeroBefore, ActaHeroAfter,
  ActivityButtonPatch, UndoToastPatch, CategoryBlockPatch,
});
