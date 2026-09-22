// EUDAIMONIA UX Patches — Tokens & Design System
// Side-by-side ANTES / DESPUÉS para que el cambio sea evidente

const EU_COLORS = {
  bg: '#09070F',
  surf: '#110E1C',
  card: '#1A1627',
  card2: '#221D32',
  border: 'rgba(201,168,76,0.15)',
  border2: 'rgba(201,168,76,0.28)',
  gold: '#C9A84C',
  goldL: '#E8C96D',
  goldBg: 'rgba(201,168,76,0.08)',
  text: '#F2EDE0',
  textOld: '#6A6050',   // dim viejo - mal contraste
  textNew: '#8A7A60',   // dim nuevo - 6:1 contraste
  mid: '#A89880',
  serif: '"Cormorant Garamond", serif',
  sans: '"DM Sans", sans-serif',
  success: '#10b981',
  warning: '#E8C96D',
  danger: '#f43f5e',
};

// ─── Shared artboard scaffold ──────────────────────────────
function Frame({ children, bg = EU_COLORS.bg, pad = 24, style = {} }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: bg, color: EU_COLORS.text,
      fontFamily: EU_COLORS.sans,
      padding: pad, overflow: 'hidden',
      ...style,
    }}>
      {children}
    </div>
  );
}

function Eyebrow({ children, color = EU_COLORS.gold, mb = 8 }) {
  return (
    <div style={{
      fontFamily: EU_COLORS.sans,
      fontSize: 11, letterSpacing: '0.18em',
      color, opacity: 0.75,
      textTransform: 'uppercase',
      marginBottom: mb, fontWeight: 500,
    }}>{children}</div>
  );
}

function SectionTitle({ children }) {
  return (
    <div style={{
      fontFamily: EU_COLORS.serif,
      fontSize: 28, fontWeight: 600,
      letterSpacing: '0.04em',
      marginBottom: 6,
    }}>{children}</div>
  );
}

// ═══════════════════════════════════════════════════════════
// TOKENS — TYPOGRAPHY SCALE
// ═══════════════════════════════════════════════════════════
function TypeScalePatch() {
  const OLD = [
    { l:'.42rem', px:'6.7px', label:'LABEL UPPERCASE' },
    { l:'.44rem', px:'7.0px', label:'sub-label' },
    { l:'.46rem', px:'7.4px', label:'caption' },
    { l:'.48rem', px:'7.7px', label:'meta info' },
    { l:'.5rem',  px:'8.0px', label:'small text' },
    { l:'.6rem',  px:'9.6px', label:'UI text' },
    { l:'.7rem',  px:'11.2px',label:'body' },
  ];
  const NEW = [
    { tok:'--fs-xs',   px:'11px', label:'LABEL · EYEBROW' },
    { tok:'--fs-sm',   px:'13px', label:'UI secundaria' },
    { tok:'--fs-base', px:'15px', label:'Texto cuerpo' },
    { tok:'--fs-lg',   px:'18px', label:'Títulos sección' },
    { tok:'--fs-xl',   px:'24px', label:'Títulos pantalla' },
    { tok:'--fs-2xl',  px:'36px', label:'Hero · Brand' },
  ];

  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #1 · TIPOGRAFÍA</Eyebrow>
      <SectionTitle>Escala de fuentes</SectionTitle>
      <div style={{ fontSize: 13, color: EU_COLORS.mid, marginBottom: 22, lineHeight:1.5 }}>
        Reemplazar <code style={{color:EU_COLORS.danger}}>.42rem – .5rem</code> ubicuos
        por una escala con tokens. Mínimo 11px.
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:18 }}>
        {/* ANTES */}
        <div style={{
          background: 'rgba(244,63,94,0.04)',
          border: `1px solid ${EU_COLORS.danger}33`,
          borderRadius: 12, padding: 16,
        }}>
          <div style={{
            fontSize:10, letterSpacing:'0.15em', color:EU_COLORS.danger,
            marginBottom: 14, fontWeight: 600,
          }}>✗ ANTES</div>
          {OLD.map(o => (
            <div key={o.l} style={{
              display:'flex', justifyContent:'space-between',
              alignItems:'baseline', padding:'8px 0',
              borderBottom: `1px solid ${EU_COLORS.border}`,
            }}>
              <span style={{ fontSize: o.l, letterSpacing:'0.15em',
                textTransform:'uppercase', color: EU_COLORS.textOld }}>{o.label}</span>
              <span style={{ fontSize: 10, color: EU_COLORS.textOld, fontFamily:'monospace' }}>
                {o.l} · {o.px}
              </span>
            </div>
          ))}
        </div>

        {/* DESPUÉS */}
        <div style={{
          background: 'rgba(16,185,129,0.05)',
          border: `1px solid ${EU_COLORS.success}33`,
          borderRadius: 12, padding: 16,
        }}>
          <div style={{
            fontSize:10, letterSpacing:'0.15em', color:EU_COLORS.success,
            marginBottom: 14, fontWeight: 600,
          }}>✓ DESPUÉS</div>
          {NEW.map(n => (
            <div key={n.tok} style={{
              display:'flex', justifyContent:'space-between',
              alignItems:'baseline', padding:'8px 0',
              borderBottom: `1px solid ${EU_COLORS.border}`,
            }}>
              <span style={{ fontSize: n.px, color: EU_COLORS.text }}>{n.label}</span>
              <span style={{ fontSize: 10, color: EU_COLORS.mid, fontFamily:'monospace' }}>
                {n.tok} · {n.px}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div style={{
        marginTop: 18, padding: '12px 14px',
        background: EU_COLORS.card, borderRadius: 8,
        fontSize: 12, color: EU_COLORS.mid, lineHeight: 1.6,
        fontFamily: 'monospace',
      }}>
        <span style={{color:EU_COLORS.gold}}>:root</span> {'{'} <br/>
        &nbsp;&nbsp;--fs-xs: 11px;  --fs-sm: 13px;  --fs-base: 15px;<br/>
        &nbsp;&nbsp;--fs-lg: 18px;  --fs-xl: 24px;  --fs-2xl: 36px;<br/>
        {'}'}
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// CONTRAST FIX
// ═══════════════════════════════════════════════════════════
function ContrastPatch() {
  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #2 · CONTRASTE</Eyebrow>
      <SectionTitle>Color secundario WCAG-safe</SectionTitle>
      <div style={{ fontSize: 13, color: EU_COLORS.mid, marginBottom: 22, lineHeight:1.5 }}>
        El color <code>--dim:#6A6050</code> sobre fondo oscuro da ~4.2:1 — falla WCAG AA.
        Subirlo a <code style={{color:EU_COLORS.gold}}>#8A7A60</code> (~6:1).
      </div>

      {[
        { label:'ANTES · --dim:#6A6050', val:EU_COLORS.textOld, ratio:'4.2:1', ok:false },
        { label:'DESPUÉS · --dim:#8A7A60', val:EU_COLORS.textNew, ratio:'6.0:1', ok:true  },
      ].map(c => (
        <div key={c.label} style={{
          padding:'16px 18px', marginBottom: 12,
          background: EU_COLORS.card,
          border: `1px solid ${c.ok ? EU_COLORS.success+'44' : EU_COLORS.danger+'44'}`,
          borderRadius: 10,
        }}>
          <div style={{
            fontSize: 11, letterSpacing:'0.12em', textTransform:'uppercase',
            color: c.ok ? EU_COLORS.success : EU_COLORS.danger, marginBottom: 8,
          }}>
            {c.ok ? '✓' : '✗'} {c.label}
          </div>
          <div style={{ fontSize: 15, color: c.val, lineHeight:1.5 }}>
            "Llevas 12 XP hoy. Faltan 3 para tu meta."
          </div>
          <div style={{ fontSize: 11, color: c.val, marginTop: 4,
            letterSpacing:'0.1em', textTransform:'uppercase' }}>
            Meta diaria · 15 XP · {c.ratio}
          </div>
        </div>
      ))}
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// CATEGORY HUE SYSTEM
// ═══════════════════════════════════════════════════════════
function CategoryHuePatch() {
  const CATS = [
    { name:'LOGOI',          virtue:'Programación', hue:120 },
    { name:'HEGEMONIKON',    virtue:'Salud',         hue:45  },
    { name:'OIKONOMIA',      virtue:'Finanzas',      hue:80  },
    { name:'COSMOPOLITISMO', virtue:'Idiomas',       hue:215 },
    { name:'PAIDEIA',        virtue:'Conocimiento',  hue:265 },
    { name:'ATARAXIA',       virtue:'Orden',         hue:155 },
    { name:'EURYTHMIA',      virtue:'Baile',         hue:330 },
    { name:'HARMA',          virtue:'Mecánica',      hue:15  },
  ];

  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #3 · CATEGORÍAS</Eyebrow>
      <SectionTitle>Hue declarado por categoría</SectionTitle>
      <div style={{ fontSize: 13, color: EU_COLORS.mid, marginBottom: 18, lineHeight:1.5 }}>
        Eliminar <code style={{color:EU_COLORS.danger}}>:nth-child(8n+x)</code> que rompe
        si reordenas. Cada virtud lleva su hue en el data layer (Python).
      </div>

      <div style={{
        display:'grid', gridTemplateColumns:'1fr 1fr', gap:8,
      }}>
        {CATS.map(c => (
          <div key={c.name} style={{
            padding:'10px 14px',
            background: `oklch(18% 0.04 ${c.hue})`,
            border: `1px solid oklch(35% 0.09 ${c.hue})`,
            borderRadius: 8,
            display:'flex', justifyContent:'space-between', alignItems:'center',
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600,
                color: `oklch(75% 0.13 ${c.hue})`, letterSpacing:'0.08em' }}>
                {c.name}
              </div>
              <div style={{ fontSize: 11, color: EU_COLORS.textNew, marginTop: 1 }}>
                {c.virtue}
              </div>
            </div>
            <div style={{
              fontFamily:'monospace', fontSize: 10,
              color: EU_COLORS.textNew, opacity: 0.7,
            }}>hue:{c.hue}</div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 16, padding: '12px 14px',
        background: EU_COLORS.card, borderRadius: 8,
        fontSize: 11, color: EU_COLORS.mid, lineHeight: 1.6,
        fontFamily: 'monospace',
      }}>
        <span style={{color:EU_COLORS.textOld}}># ec_constants.py o data.py</span><br/>
        CATEGORIES = {'{'}<br/>
        &nbsp;&nbsp;'LOGOI':       {'{ "hue": 120, "virtue": "Programación" },'}<br/>
        &nbsp;&nbsp;'HEGEMONIKON': {'{ "hue":  45, "virtue": "Salud" },'}<br/>
        &nbsp;&nbsp;...<br/>
        {'}'}
      </div>
    </Frame>
  );
}

// ═══════════════════════════════════════════════════════════
// UPPERCASE DIET
// ═══════════════════════════════════════════════════════════
function UppercaseDietPatch() {
  return (
    <Frame pad={28}>
      <Eyebrow>PATCH #4 · TIPOGRAFÍA</Eyebrow>
      <SectionTitle>Dieta de uppercase</SectionTitle>
      <div style={{ fontSize: 13, color: EU_COLORS.mid, marginBottom: 22, lineHeight:1.5 }}>
        Cada label, badge, sub-título es uppercase + tracked. Pierde poder.
        Limitar a <strong>eyebrows</strong> y <strong>chips de estado</strong>.
      </div>

      {/* ANTES */}
      <div style={{
        padding: 18, marginBottom: 14,
        background: 'rgba(244,63,94,0.04)',
        border: `1px solid ${EU_COLORS.danger}33`,
        borderRadius: 12,
      }}>
        <div style={{ fontSize:10, letterSpacing:'0.15em', color:EU_COLORS.danger,
          marginBottom: 12, fontWeight: 600 }}>✗ ANTES — 6 niveles uppercase</div>
        <div style={{ fontSize:10, letterSpacing:'0.18em',
          textTransform:'uppercase', color:EU_COLORS.gold, marginBottom:4 }}>
          MARTES 19 DE MAYO
        </div>
        <div style={{ fontSize:24, fontFamily:EU_COLORS.serif, marginBottom:8 }}>Acta Diurna</div>
        <div style={{ fontSize:10, letterSpacing:'0.16em',
          textTransform:'uppercase', color:EU_COLORS.textOld, marginBottom: 10 }}>
          REGISTRO DE ACTIVIDADES Y VIRTUDES · PROGRESO = GENERA EC · ALTO = TRANSFORMACIÓN
        </div>
        <div style={{ fontSize:10, letterSpacing:'0.18em',
          textTransform:'uppercase', color:EU_COLORS.textOld, marginBottom: 6 }}>HEGEMONIKON</div>
        <div style={{ fontSize:11, letterSpacing:'0.16em',
          textTransform:'uppercase', color:EU_COLORS.textOld }}>PRÁCTICA DIARIA</div>
      </div>

      {/* DESPUÉS */}
      <div style={{
        padding: 18,
        background: 'rgba(16,185,129,0.05)',
        border: `1px solid ${EU_COLORS.success}33`,
        borderRadius: 12,
      }}>
        <div style={{ fontSize:10, letterSpacing:'0.15em', color:EU_COLORS.success,
          marginBottom: 12, fontWeight: 600 }}>✓ DESPUÉS — 2 niveles uppercase</div>
        <div style={{ fontSize:11, letterSpacing:'0.18em',
          textTransform:'uppercase', color:EU_COLORS.gold, marginBottom:4 }}>
          MARTES 19 DE MAYO
        </div>
        <div style={{ fontSize:28, fontFamily:EU_COLORS.serif, marginBottom:6, fontWeight:600 }}>
          Acta Diurna
        </div>
        <div style={{ fontSize:14, color:EU_COLORS.textNew, marginBottom: 14, lineHeight:1.5 }}>
          Registro de actividades y virtudes. <span style={{color:EU_COLORS.success}}>Progreso</span> genera
          EC; <span style={{color:EU_COLORS.warning}}>Alto</span> es transformación.
        </div>
        <div style={{
          display:'inline-block',
          fontSize:11, letterSpacing:'0.12em', textTransform:'uppercase',
          color:'oklch(75% 0.13 45)',
          background:'oklch(18% 0.04 45)',
          border:'1px solid oklch(35% 0.09 45)',
          padding:'4px 10px', borderRadius: 100, marginBottom: 10,
        }}>HEGEMONIKON</div>
        <div style={{ fontSize:18, fontFamily:EU_COLORS.serif, fontStyle:'italic',
          color:EU_COLORS.text }}>Práctica diaria</div>
      </div>
    </Frame>
  );
}

Object.assign(window, {
  EU_COLORS, Frame, Eyebrow, SectionTitle,
  TypeScalePatch, ContrastPatch, CategoryHuePatch, UppercaseDietPatch,
});
