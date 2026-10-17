// EUDAIMONIA UX Patches — Navigation, Dashboard, Command Palette

// ═══════════════════════════════════════════════════════════
// DASHBOARD HOY — la pantalla "/" actualmente vacía
// ═══════════════════════════════════════════════════════════
function DashboardHoyPatch() {
  const c = EU_COLORS;
  const xp = 12, goal = 15;

  return (
    <Frame pad={20}>
      <div style={{ maxWidth: 440, margin: '0 auto' }}>
        <Eyebrow color={c.gold}>NUEVO · DASHBOARD /</Eyebrow>
        <div style={{ fontFamily:c.serif, fontSize: 22, marginBottom: 4 }}>
          Buenos días, Gio.
        </div>
        <div style={{ fontSize: 12, color: c.textNew, marginBottom: 18 }}>
          Martes 19 de mayo · día 12 de tu racha
        </div>

        {/* XP del día - foco principal */}
        <div style={{
          background:'linear-gradient(140deg,#1C1830,#110F20)',
          border:`1px solid ${c.border2}`, borderRadius: 16,
          padding: '20px 20px 18px', marginBottom: 14,
          position: 'relative', overflow:'hidden',
        }}>
          <div style={{ fontSize:11, letterSpacing:'0.2em', color:c.gold,
            textTransform:'uppercase', opacity:0.7, marginBottom:6 }}>HOY</div>
          <div style={{ display:'flex', alignItems:'baseline', gap: 10, marginBottom: 12 }}>
            <div style={{ fontFamily:c.serif, fontSize: 52, fontWeight: 600,
              color: c.goldL, lineHeight: 1 }}>{xp}</div>
            <div style={{ fontSize: 14, color: c.mid }}>
              / {goal} XP
            </div>
          </div>
          <div style={{ height: 5, background:'rgba(201,168,76,0.08)',
            borderRadius: 3, overflow:'hidden', marginBottom: 8 }}>
            <div style={{ width:`${(xp/goal)*100}%`, height:'100%',
              background:'linear-gradient(90deg,#7A5520,#C9A84C,#E8C96D)',
              boxShadow:'0 0 10px rgba(201,168,76,0.5)' }}/>
          </div>
          <div style={{ display:'flex', justifyContent:'space-between' }}>
            <span style={{ fontSize:11, color:c.textNew }}>
              ⚔️ Hierro · 3 categorías
            </span>
            <span style={{ fontSize:11, color:c.gold }}>
              3 XP para Oro
            </span>
          </div>
        </div>

        {/* Próximas acciones */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display:'flex', justifyContent:'space-between',
            alignItems:'center', marginBottom: 10 }}>
            <div style={{ fontSize:11, letterSpacing:'0.15em', color:c.textNew,
              textTransform:'uppercase' }}>Próximas 3 acciones</div>
            <div style={{ fontSize:12, color:c.gold }}>Ver todas →</div>
          </div>
          {[
            { l:'Lección 100 Días Python', xp:2, cat:'LOGOI', hue:120 },
            { l:'Práctica de baile 30 min', xp:2, cat:'EURYTHMIA', hue:330 },
            { l:'Registrar gastos', xp:2, cat:'OIKONOMIA', hue:80 },
          ].map((a,i) => {
            const acc = `oklch(65% 0.15 ${a.hue})`;
            return (
              <div key={i} style={{
                background: c.card, border:`1px solid ${c.border}`,
                borderRadius: 10, padding:'12px 14px', marginBottom: 6,
                display:'flex', alignItems:'center', gap: 11,
              }}>
                <div style={{ width:18, height:18, borderRadius:5,
                  border:`1.5px solid ${c.border2}` }}/>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: c.text }}>{a.l}</div>
                  <div style={{ fontSize:10, color: acc, marginTop:2,
                    letterSpacing:'0.08em', textTransform:'uppercase' }}>{a.cat}</div>
                </div>
                <span style={{ fontSize: 12, color: c.gold }}>+{a.xp}</span>
              </div>
            );
          })}
        </div>

        {/* Micro hábito sugerido + Quote */}
        <div style={{
          background: 'oklch(20% 0.05 45)',
          border: '1px solid oklch(35% 0.09 45)',
          borderRadius: 12, padding: 14, marginBottom: 12,
          display:'flex', alignItems:'center', gap: 12,
        }}>
          <div style={{ fontSize: 22 }}>✦</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize:11, color:'oklch(75% 0.13 45)',
              letterSpacing:'0.12em', textTransform:'uppercase' }}>
              Sugerencia del día
            </div>
            <div style={{ fontSize: 13, color: c.text, marginTop: 2 }}>
              Solo te falta <strong>Skin Care</strong> para terminar Hegemonikon.
            </div>
          </div>
          <button style={{
            background:'transparent', border:`1px solid oklch(45% 0.1 45)`,
            color:'oklch(75% 0.13 45)', padding:'6px 12px', borderRadius: 7,
            fontSize: 11, letterSpacing:'0.1em', cursor:'pointer',
            fontFamily: c.sans,
          }}>+2 XP</button>
        </div>

        <div style={{
          padding:'14px 16px', background:'rgba(201,168,76,0.04)',
          border:`1px solid ${c.border}`, borderLeft:`3px solid ${c.gold}`,
          borderRadius:'0 10px 10px 0',
        }}>
          <div style={{ fontFamily:c.serif, fontStyle:'italic', fontSize: 15,
            color: c.text, lineHeight: 1.55 }}>
            "La felicidad de tu vida depende de la calidad de tus pensamientos."
          </div>
          <div style={{ fontSize:10, letterSpacing:'0.12em', color:c.gold,
            textTransform:'uppercase', marginTop: 6, opacity:0.7 }}>
            — Marco Aurelio
          </div>
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// BOTTOM NAV MOBILE
// ═══════════════════════════════════════════════════════════
function BottomNavPatch() {
  const c = EU_COLORS;
  const tabs = [
    { id:'home', label:'Ἀρχή', sub:'Inicio', active: true },
    { id:'acta', label:'Acta',  sub:'Diurna' },
    { id:'gtd',  label:'Πρᾶξις',sub:'Praxis' },
    { id:'mod',  label:'Κόσμος',sub:'Módulos' },
    { id:'self', label:'Αὐτός', sub:'Perfil' },
  ];

  return (
    <Frame pad={20}>
      <Eyebrow>PATCH #11 · NAVEGACIÓN</Eyebrow>
      <SectionTitle>Bottom nav mobile</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        En desktop sidebar; en mobile (&lt;1024px) un nav inferior. 5 destinos máximo,
        con etiqueta griega + sub en español.
      </div>

      {/* Mock device */}
      <div style={{
        width: 320, height: 480, margin: '0 auto',
        background: c.bg, border: `1px solid ${c.border2}`,
        borderRadius: 28, position:'relative', overflow:'hidden',
        boxShadow:'0 14px 40px rgba(0,0,0,0.6)',
      }}>
        {/* Status bar */}
        <div style={{ padding:'10px 18px', display:'flex',
          justifyContent:'space-between', fontSize: 10, color: c.text }}>
          <span>9:41</span><span>EUDAIMONIA</span><span>100%</span>
        </div>
        {/* Body placeholder */}
        <div style={{ padding: 18 }}>
          <div style={{ fontSize:11, letterSpacing:'0.2em', color:c.gold, opacity:0.7,
            textTransform:'uppercase', marginBottom: 4 }}>Martes 19</div>
          <div style={{ fontFamily:c.serif, fontSize: 22, fontWeight:600 }}>
            Buenos días.
          </div>
          <div style={{ marginTop: 18, height: 100,
            background:'linear-gradient(140deg,#1C1830,#110F20)',
            border:`1px solid ${c.border}`, borderRadius: 14 }}/>
          <div style={{ marginTop: 12, height: 60,
            background:c.card, border:`1px solid ${c.border}`, borderRadius: 10 }}/>
          <div style={{ marginTop: 8, height: 60,
            background:c.card, border:`1px solid ${c.border}`, borderRadius: 10 }}/>
        </div>

        {/* Bottom nav */}
        <div style={{
          position:'absolute', bottom: 0, left: 0, right: 0,
          background:'rgba(9,7,15,0.97)',
          backdropFilter:'blur(20px)',
          borderTop:`1px solid ${c.border}`,
          display:'flex', padding:'8px 0 14px',
        }}>
          {tabs.map(t => (
            <div key={t.id} style={{
              flex: 1, display:'flex', flexDirection:'column',
              alignItems:'center', padding:'6px 2px', cursor:'pointer',
            }}>
              <div style={{
                fontFamily: c.serif, fontSize: 16, lineHeight: 1,
                color: t.active ? c.gold : c.textNew,
              }}>{t.label}</div>
              <div style={{
                fontSize: 9, letterSpacing:'0.1em', textTransform:'uppercase',
                color: t.active ? c.gold : c.textNew, opacity: t.active ? 1 : 0.55,
                marginTop: 3,
              }}>{t.sub}</div>
              {t.active && <div style={{
                width: 18, height: 2, borderRadius: 1, background: c.gold,
                marginTop: 4, boxShadow:`0 0 6px ${c.gold}`,
              }}/>}
            </div>
          ))}
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// COMMAND PALETTE (Cmd-K)
// ═══════════════════════════════════════════════════════════
function CommandPalettePatch() {
  const c = EU_COLORS;
  const items = [
    { i:'⌨️', l:'Capturar idea en Inbox', s:'GTD · Quick capture', kbd:['C'] },
    { i:'✓',  l:'Registrar: Meditar (+2 XP)', s:'Acta Diurna · Hegemonikon' },
    { i:'💰', l:'Ir a Finanzas', s:'Oikonomia · Balance' },
    { i:'🚗', l:'Ir a HARMA', s:'Mecánica · Vehículo' },
    { i:'🔄', l:'Cambiar tema día/noche', s:'Sistema', kbd:['⇧','T'] },
    { i:'⚙️', l:'Configuración del perfil', s:'Sistema' },
  ];

  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #12 · COMMAND PALETTE</Eyebrow>
      <SectionTitle>Cmd-K para todo</SectionTitle>
      <div style={{ fontSize: 13, color: c.mid, marginBottom: 22, lineHeight:1.5 }}>
        Con 10+ módulos, command palette es esencial. Fuzzy search en rutas + acciones.
      </div>

      {/* Backdrop */}
      <div style={{
        background:'rgba(9,7,15,0.7)', borderRadius: 14, padding: 24,
        backdropFilter:'blur(8px)',
      }}>
        <div style={{
          background: c.card, border: `1px solid ${c.border2}`,
          borderRadius: 14, overflow:'hidden',
          boxShadow:'0 24px 60px rgba(0,0,0,0.6)',
        }}>
          {/* Search */}
          <div style={{
            display:'flex', alignItems:'center', gap: 12,
            padding:'14px 18px', borderBottom: `1px solid ${c.border}`,
          }}>
            <span style={{ fontSize: 18, color: c.gold }}>⌘</span>
            <input
              defaultValue=""
              placeholder="Busca acción, página o atajo…"
              readOnly
              style={{
                flex: 1, background:'transparent', border:'none', outline:'none',
                color: c.text, fontFamily: c.sans, fontSize: 15,
              }}
            />
            <kbd style={{
              fontSize: 11, padding:'2px 8px',
              background: c.card2, border:`1px solid ${c.border}`,
              borderRadius: 6, color: c.textNew, fontFamily:'monospace',
            }}>ESC</kbd>
          </div>

          {/* Section: actions */}
          <div style={{ padding:'10px 18px 4px', fontSize: 11,
            letterSpacing:'0.12em', color: c.textNew, textTransform:'uppercase' }}>
            Acciones rápidas
          </div>
          {items.slice(0, 2).map((it, i) => (
            <div key={i} style={{
              padding:'10px 18px',
              background: i === 0 ? 'rgba(201,168,76,0.08)' : 'transparent',
              borderLeft: i === 0 ? `2px solid ${c.gold}` : '2px solid transparent',
              display:'flex', alignItems:'center', gap: 12, cursor:'pointer',
            }}>
              <div style={{ fontSize: 16 }}>{it.i}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, color: c.text }}>{it.l}</div>
                <div style={{ fontSize: 11, color: c.textNew, marginTop: 1 }}>{it.s}</div>
              </div>
              {it.kbd && (
                <div style={{ display:'flex', gap: 4 }}>
                  {it.kbd.map(k => (
                    <kbd key={k} style={{
                      fontSize: 11, padding:'2px 8px',
                      background: c.card2, border:`1px solid ${c.border}`,
                      borderRadius: 5, color: c.textNew, fontFamily:'monospace',
                    }}>{k}</kbd>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Section: navigate */}
          <div style={{ padding:'10px 18px 4px', fontSize: 11,
            letterSpacing:'0.12em', color: c.textNew, textTransform:'uppercase' }}>
            Ir a…
          </div>
          {items.slice(2, 5).map((it, i) => (
            <div key={i} style={{
              padding:'10px 18px',
              display:'flex', alignItems:'center', gap: 12, cursor:'pointer',
            }}>
              <div style={{ fontSize: 16 }}>{it.i}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, color: c.text }}>{it.l}</div>
                <div style={{ fontSize: 11, color: c.textNew, marginTop: 1 }}>{it.s}</div>
              </div>
              {it.kbd && (
                <div style={{ display:'flex', gap: 4 }}>
                  {it.kbd.map(k => (
                    <kbd key={k} style={{
                      fontSize: 11, padding:'2px 8px',
                      background: c.card2, border:`1px solid ${c.border}`,
                      borderRadius: 5, color: c.textNew, fontFamily:'monospace',
                    }}>{k}</kbd>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Footer hint */}
          <div style={{
            padding:'10px 18px', borderTop: `1px solid ${c.border}`,
            display:'flex', gap: 18, fontSize: 11, color: c.textNew,
          }}>
            <span><kbd style={{
              fontSize: 10, padding:'1px 6px', background: c.card2,
              border:`1px solid ${c.border}`, borderRadius: 4,
              fontFamily:'monospace',
            }}>↑↓</kbd> navegar</span>
            <span><kbd style={{
              fontSize: 10, padding:'1px 6px', background: c.card2,
              border:`1px solid ${c.border}`, borderRadius: 4,
              fontFamily:'monospace',
            }}>⏎</kbd> seleccionar</span>
            <span style={{ marginLeft:'auto' }}>
              <kbd style={{
                fontSize: 10, padding:'1px 6px', background: c.card2,
                border:`1px solid ${c.border}`, borderRadius: 4,
                fontFamily:'monospace',
              }}>⌘ K</kbd> abrir/cerrar
            </span>
          </div>
        </div>
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// SIDEBAR REDISEÑO (legible, no .68rem)
// ═══════════════════════════════════════════════════════════
function SidebarPatch() {
  const c = EU_COLORS;

  return (
    <Frame pad={0} style={{ display:'flex' }}>
      <div style={{ padding: 24, flex: 1 }}>
        <Eyebrow>PATCH #13 · SIDEBAR</Eyebrow>
        <SectionTitle>Sidebar con jerarquía clara</SectionTitle>
        <div style={{ fontSize: 13, color: c.mid, marginBottom: 14, lineHeight:1.5 }}>
          Items principales 15px (era ~10.9px) · sub-items 13px · iconos 18px.
        </div>
        <div style={{ fontSize: 12, color: c.textNew, lineHeight: 1.7 }}>
          Reagrupar por <strong>verbo de uso</strong>, no por categoría técnica:<br/>
          <span style={{color:c.gold}}>HOY</span> — Inicio, Acta Diurna, Praxis<br/>
          <span style={{color:c.gold}}>MÓDULOS</span> — Oikonomia, Hegemonikon, Cosmopolitismo, Harma<br/>
          <span style={{color:c.gold}}>SISTEMA</span> — Logros, Recompensas, Perfil
        </div>
      </div>

      {/* Sidebar mock */}
      <div style={{
        width: 240, background:'#0C0A16', borderLeft:`1px solid ${c.border}`,
        padding:'24px 0', display:'flex', flexDirection:'column',
      }}>
        <div style={{ padding:'0 18px 14px', borderBottom:`1px solid ${c.border}` }}>
          <div style={{ fontSize:10, letterSpacing:'0.28em', color:c.gold, opacity:0.65,
            textTransform:'uppercase', marginBottom: 4 }}>SISTEMA PERSONAL</div>
          <div style={{ fontFamily:c.serif, fontSize: 22, fontWeight:600,
            letterSpacing:'0.12em' }}>EUDAIMONIA</div>
        </div>

        <div style={{ padding: 12 }}>
          <div style={{ fontSize:11, letterSpacing:'0.2em',
            color:c.textNew, textTransform:'uppercase',
            padding:'8px 10px 6px' }}>Hoy</div>
          {[
            { i:'⌂', l:'Inicio',      s:'Dashboard',    a:true },
            { i:'☰', l:'Acta Diurna', s:'Actividades' },
            { i:'✚', l:'Praxis',      s:'GTD' },
          ].map(item => (
            <div key={item.l} style={{
              display:'flex', alignItems:'center', gap: 12,
              padding:'10px 12px', borderRadius: 8,
              background: item.a ? c.goldBg : 'transparent',
              borderLeft: item.a ? `2px solid ${c.gold}` : '2px solid transparent',
              color: item.a ? c.gold : c.mid,
              marginBottom: 2, cursor:'pointer',
            }}>
              <span style={{ fontSize: 16, width: 18, textAlign:'center' }}>{item.i}</span>
              <div>
                <div style={{ fontSize: 14 }}>{item.l}</div>
                <div style={{ fontSize: 11, color: c.textNew, marginTop: 1 }}>{item.s}</div>
              </div>
            </div>
          ))}

          <div style={{ fontSize:11, letterSpacing:'0.2em',
            color:c.textNew, textTransform:'uppercase',
            padding:'14px 10px 6px' }}>Módulos</div>
          {[
            { i:'◆', l:'Oikonomia',     s:'Finanzas' },
            { i:'◇', l:'Hegemonikon',   s:'Salud' },
            { i:'⊕', l:'Cosmopolitismo',s:'Idiomas' },
            { i:'⚙', l:'Harma',         s:'Vehículo' },
          ].map(item => (
            <div key={item.l} style={{
              display:'flex', alignItems:'center', gap: 12,
              padding:'10px 12px', borderRadius: 8,
              color: c.mid, marginBottom: 2, cursor:'pointer',
            }}>
              <span style={{ fontSize: 16, width: 18, textAlign:'center' }}>{item.i}</span>
              <div>
                <div style={{ fontSize: 14 }}>{item.l}</div>
                <div style={{ fontSize: 11, color: c.textNew, marginTop: 1 }}>{item.s}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Frame>
  );
}

Object.assign(window, {
  DashboardHoyPatch, BottomNavPatch, CommandPalettePatch, SidebarPatch,
});
