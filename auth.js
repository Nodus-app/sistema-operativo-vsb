// VSB Distribuciones - Dashboard Operativo - app.js
// Login cosmetico (protege por UX, no es seguridad real: repo publico, todos los
// datos de todos los vendedores viajan igual en el HTML sea cual sea el login usado).
var USERS = { 'sup': { pass: 'VsbSup2026!', name: 'Supervisor' } };
var ROLE = 'sup';       // 'sup' | 'vendedor'
var VEND_COD = null;
var TABS_VENDEDOR = ['ventas', 'rechazos', 'rentabilidad', 'descuentos', 'objetivo', 'clientes', 'producto'];  // unicas visibles para rol vendedor (evolucion queda solo para supervisor)

function F(n) {
  n = Number(n) || 0;
  return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function FI(n) { return (Number(n) || 0).toLocaleString('es-AR'); }
function P(n) { return (Number(n) || 0).toFixed(1) + '%'; }

function pctClass(pct) {
  if (pct >= 15) return 'br';
  if (pct >= 7) return 'by';
  return 'bg';
}

function KPI(label, value, cls) {
  return '<div class="kpi"><div class="kpi-v" style="color:' + (cls || '#e3ecf7') + '">' + value + '</div><div class="kpi-l">' + label + '</div></div>';
}

function doLogin() {
  var uRaw = (document.getElementById('lu').value || '').trim();
  var u = uRaw.toLowerCase();
  var p = (document.getElementById('lp').value || '').trim();
  var usr = USERS[u];

  if (usr && p === usr.pass) {
    ROLE = 'sup'; VEND_COD = null;
    sessionStorage.setItem('vsb_auth', 'sup');
    entrar();
    return;
  }

  // Vendedor: usuario = numero de vendedor, clave = numero repetido (ej. vendedor 3 -> "33")
  if (/^\d+$/.test(uRaw) && D_VVALIDOS.indexOf(uRaw) !== -1 && p === uRaw + uRaw) {
    ROLE = 'vendedor'; VEND_COD = uRaw;
    sessionStorage.setItem('vsb_auth', 'vendedor:' + uRaw);
    entrar();
    return;
  }

  document.getElementById('lerr').style.display = 'block';
}
function entrar() {
  document.getElementById('login-overlay').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  initApp();
}
function doLogout() {
  sessionStorage.removeItem('vsb_auth');
  location.reload();
}

// ---------- PERIODO (mes) ----------
var MES_ACTIVO = null;
function curData() {
  var fuente = ROLE === 'vendedor' ? ((D_VEND_DATA[VEND_COD] || {})[MES_ACTIVO]) : D_DATA[MES_ACTIVO];
  return fuente || {
    kpis: {}, prov: [], chofer: [], camion: [],
    kpis_camion: {}, prov_camion: {}, chofer_camion: {}, chofer_prov_camion: {},
    motivo: [], motivo_prov: {}, motivo_camion: {}, motivo_prov_camion: {}, chofer_prov: {}, routes: [], cli: {},
    rent_prov: [], rent_chofer: [], rent_prov_camion: {}, rent_chofer_camion: {}, rent_total_camion: {},
    desc_prov: [], desc_chofer: [], desc_prov_camion: {}, desc_chofer_camion: {},
    geo: [], geo_camion: {}, vendedor: [], vendedor_camion: {},
    producto: [], rubro: [], producto_camion: {}, rubro_camion: {},
    clientes: [], clientes_camion: {}, clientes_camion_anterior: {},
    provs: [], chs: [], camiones: [],
  };
}

// ---------- CAMION (filtro global "Excluir Camion", afecta TODAS las pestañas) ----------
var CAM_EXCL = '';
function initCamSelector() {
  var d = curData();
  var sel = document.getElementById('hdr-cam-f');
  var prev = CAM_EXCL;
  sel.innerHTML = '<option value="">Ninguno excluido</option>' + (d.camiones || []).map(function (c) {
    return '<option value="' + c + '">' + c + '</option>';
  }).join('');
  if ((d.camiones || []).indexOf(prev) !== -1) {
    sel.value = prev;
    CAM_EXCL = prev;
  } else {
    sel.value = '';
    CAM_EXCL = '';
  }
}
function onCamChange() {
  CAM_EXCL = document.getElementById('hdr-cam-f').value;
  // invalida el cache de "ya renderizado" de todas las pestañas: si no, al volver a una pestaña
  // ya visitada antes de tocar el filtro, goTab() no la vuelve a pintar y queda con datos viejos.
  TAB_INIT = {};
  rerenderCurrentTab();
  TAB_INIT[CURRENT_TAB] = true;
}

function initMesSelector() {
  var sel = document.getElementById('hdr-mes');
  sel.innerHTML = D_MESES.map(function (m) {
    return '<option value="' + m + '">' + (D_MES_LABEL[m] || m) + '</option>';
  }).join('');
  MES_ACTIVO = D_MES_ACTUAL || (D_MESES[0] || null);
  sel.value = MES_ACTIVO;
}
function onMesChange() {
  MES_ACTIVO = document.getElementById('hdr-mes').value;
  RUTA_SEL = null;
  TAB_INIT = {};
  initCamSelector();
  rerenderCurrentTab();
  TAB_INIT[CURRENT_TAB] = true;
}

function rerenderCurrentTab() {
  if (CURRENT_TAB === 'ventas') renderVentas();
  if (CURRENT_TAB === 'ruta') initRuta();
  if (CURRENT_TAB === 'rechazos') renderRechazos();
  if (CURRENT_TAB === 'rentabilidad') renderRentabilidad();
  if (CURRENT_TAB === 'descuentos') renderDescuentos();
  if (CURRENT_TAB === 'geografia') renderGeografia();
  if (CURRENT_TAB === 'objetivo') renderObjetivo();
  if (CURRENT_TAB === 'evolucion') renderEvolucion();
  if (CURRENT_TAB === 'interanual') renderInteranual();
  if (CURRENT_TAB === 'nocompradores') renderNoCompradores();
  if (CURRENT_TAB === 'clientes') renderClientes();
  if (CURRENT_TAB === 'producto') renderProducto();
}

// ---------- TABS ----------
var CURRENT_TAB = 'ventas';
var TAB_INIT = {};
function goTab(id, btn) {
  document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('on'); });
  document.querySelectorAll('.sec').forEach(function (s) { s.classList.remove('on'); });
  btn.classList.add('on');
  document.getElementById('sec-' + id).classList.add('on');
  CURRENT_TAB = id;
  if (!TAB_INIT[id]) {
    TAB_INIT[id] = true;
    rerenderCurrentTab();
  }
}

function initApp() {
  applyRoleUI();
  initMesSelector();
  initCamSelector();
  renderVentas();
  TAB_INIT = { ventas: true };
  CURRENT_TAB = 'ventas';
  document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('on'); });
  document.querySelectorAll('.sec').forEach(function (s) { s.classList.remove('on'); });
  document.getElementById('sec-ventas').classList.add('on');
  var firstTab = document.querySelector('.tabs .tab:not([style*="display: none"])');
  if (firstTab) firstTab.classList.add('on');
}

function applyRoleUI() {
  var badge = document.getElementById('hdr-rol');
  document.querySelectorAll('.tabs .tab').forEach(function (btn) {
    var id = (btn.getAttribute('onclick') || '').match(/goTab\('(\w+)'/);
    id = id ? id[1] : null;
    var visible = ROLE === 'sup' || TABS_VENDEDOR.indexOf(id) !== -1;
    btn.style.display = visible ? '' : 'none';
  });
  if (ROLE === 'vendedor') {
    badge.textContent = '— ' + (D_VNOM[VEND_COD] || ('Vendedor ' + VEND_COD));
  } else {
    badge.textContent = '— Supervisor';
  }
}

// ---------- VENTAS ----------

// Helpers para el filtro "Excluir Camion": los datos vienen precalculados por camion
// desde Python (d.kpis_camion / d.prov_camion / d.chofer_camion / d.chofer_prov_camion) y
// acá se suman todos los camiones MENOS el excluido. Venta/rechazo/cambio/unidades/entregas
// son sumas -> se pueden acumular camion por camion. clientes/choferes/repartos son conteos
// DISTINCT -> hay que unionar los sets de ids (no alcanza con restar el conteo del camion excluido,
// porque un mismo cliente puede haber sido atendido por más de un camion en el mes).
function camKpisExcluyendo(kpisCamion, excl) {
  var venta_neta = 0, rechazo_monto = 0, cambio_monto = 0, comprobantes = 0, rechazados = 0, cambios_cant = 0;
  var cli = {}, cho = {}, rep = {};
  Object.keys(kpisCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var k = kpisCamion[cam];
    venta_neta += k.venta_neta; rechazo_monto += k.rechazo_monto; cambio_monto += k.cambio_monto;
    comprobantes += k.comprobantes; rechazados += k.rechazados; cambios_cant += k.cambios_cant;
    (k.clientes || []).forEach(function (id) { cli[id] = 1; });
    (k.choferes || []).forEach(function (id) { cho[id] = 1; });
    (k.repartos || []).forEach(function (id) { rep[id] = 1; });
  });
  var bruta = venta_neta + rechazo_monto + cambio_monto;
  return {
    venta_neta: venta_neta, rechazo_monto: rechazo_monto, cambio_monto: cambio_monto,
    pct_rechazo: bruta ? (rechazo_monto / bruta * 100) : 0,
    pct_cambio: bruta ? (cambio_monto / bruta * 100) : 0,
    comprobantes: comprobantes, rechazados: rechazados, cambios_cant: cambios_cant,
    clientes: Object.keys(cli).length, choferes: Object.keys(cho).length, repartos: Object.keys(rep).length,
  };
}

// byCamion: {camion: {grupo: {venta,rechazo,cambio,...extraKeys}}} -> suma todos los camiones
// menos "excl" y devuelve {grupo: {venta,rechazo,cambio,...}} (sin ordenar).
function camAggExcluyendo(byCamion, excl, extraKeys) {
  var agg = {};
  Object.keys(byCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var grupos = byCamion[cam];
    Object.keys(grupos).forEach(function (g) {
      var c = grupos[g];
      var a = agg[g];
      if (!a) {
        a = agg[g] = { venta: 0, rechazo: 0, cambio: 0 };
        (extraKeys || []).forEach(function (k) { a[k] = 0; });
      }
      a.venta += c.venta || 0; a.rechazo += c.rechazo || 0; a.cambio += c.cambio || 0;
      (extraKeys || []).forEach(function (k) { a[k] += c[k] || 0; });
    });
  });
  return agg;
}

function camProvListExcluyendo(provCamion, excl) {
  var agg = camAggExcluyendo(provCamion, excl, ['unidades']);
  var out = Object.keys(agg).map(function (p) {
    var a = agg[p], bruta = a.venta + a.rechazo + a.cambio;
    return {
      proveedor: p, venta: a.venta, rechazo: a.rechazo, cambio: a.cambio, unidades: a.unidades,
      pct_rechazo: bruta ? (a.rechazo / bruta * 100) : 0, pct_cambio: bruta ? (a.cambio / bruta * 100) : 0,
    };
  });
  out.sort(function (a, b) { return b.venta - a.venta; });
  return out;
}

function camChoferListExcluyendo(choferCamion, excl) {
  var agg = camAggExcluyendo(choferCamion, excl, ['entregas', 'rechazos', 'cambios']);
  var out = Object.keys(agg).map(function (c) {
    var a = agg[c], bruta = a.venta + a.rechazo + a.cambio, total = a.entregas + a.rechazos + a.cambios;
    return {
      chofer: c, venta: a.venta, rechazo: a.rechazo, cambio: a.cambio,
      pct_rechazo: bruta ? (a.rechazo / bruta * 100) : 0, pct_cambio: bruta ? (a.cambio / bruta * 100) : 0,
      efectividad: total ? (a.entregas / total * 100) : 0,
    };
  });
  out.sort(function (a, b) { return b.venta - a.venta; });
  return out;
}

function camMotivoListExcluyendo(motivoCamion, excl) {
  var agg = {};
  Object.keys(motivoCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var motivos = motivoCamion[cam];
    Object.keys(motivos).forEach(function (m) {
      var v = motivos[m];
      var a = agg[m] || (agg[m] = { motivo: m, cantidad: 0, importe: 0 });
      a.cantidad += v.cantidad || 0; a.importe += v.importe || 0;
    });
  });
  var out = Object.keys(agg).map(function (m) { return agg[m]; });
  var total = out.reduce(function (s, a) { return s + a.importe; }, 0) || 1;
  out.forEach(function (a) { a.pct = a.importe / total * 100; });
  out.sort(function (a, b) { return b.importe - a.importe; });
  return out;
}

function camRentListExcluyendo(byCamion, excl) {
  var agg = {};
  Object.keys(byCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var grupos = byCamion[cam];
    Object.keys(grupos).forEach(function (g) {
      var c = grupos[g];
      var a = agg[g] || (agg[g] = { grupo: g, venta: 0, costo: 0 });
      a.venta += c.venta || 0; a.costo += c.costo || 0;
    });
  });
  var out = Object.keys(agg).map(function (g) { return agg[g]; });
  out.forEach(function (a) {
    a.rentabilidad = a.venta - a.costo;
    a.pct_rentabilidad = a.venta ? (a.rentabilidad / a.venta * 100) : 0;
  });
  out.sort(function (a, b) { return b.rentabilidad - a.rentabilidad; });
  return out;
}

function camDescListExcluyendo(byCamion, excl) {
  var agg = {};
  Object.keys(byCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var grupos = byCamion[cam];
    Object.keys(grupos).forEach(function (g) {
      var c = grupos[g];
      var a = agg[g] || (agg[g] = { grupo: g, venta_sin_desc: 0, descuento: 0 });
      a.venta_sin_desc += c.venta_sin_desc || 0; a.descuento += c.descuento || 0;
    });
  });
  var out = Object.keys(agg).map(function (g) { return agg[g]; });
  out.forEach(function (a) { a.pct_descuento = a.venta_sin_desc ? (a.descuento / a.venta_sin_desc * 100) : 0; });
  out.sort(function (a, b) { return b.descuento - a.descuento; });
  return out;
}

function camGeoListExcluyendo(geoCamion, excl) {
  var agg = {};
  Object.keys(geoCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var locs = geoCamion[cam];
    Object.keys(locs).forEach(function (loc) {
      var v = locs[loc];
      var a = agg[loc] || (agg[loc] = { localidad: loc, venta: 0, rechazo: 0, cambio: 0, clientesSet: {} });
      a.venta += v.venta || 0; a.rechazo += v.rechazo || 0; a.cambio += v.cambio || 0;
      (v.clientes || []).forEach(function (id) { a.clientesSet[id] = 1; });
    });
  });
  var out = Object.keys(agg).map(function (loc) {
    var a = agg[loc], bruta = a.venta + a.rechazo + a.cambio;
    return {
      localidad: loc, venta: a.venta, rechazo: a.rechazo, cambio: a.cambio,
      pct_rechazo: bruta ? (a.rechazo / bruta * 100) : 0, clientes: Object.keys(a.clientesSet).length,
    };
  });
  out.sort(function (a, b) { return b.venta - a.venta; });
  return out;
}

function camVendedorListExcluyendo(vendCamion, baseList, excl) {
  var agg = {};
  Object.keys(vendCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var cods = vendCamion[cam];
    Object.keys(cods).forEach(function (cod) {
      var v = cods[cod];
      var a = agg[cod] || (agg[cod] = { venta: 0, rechazo: 0, cambio: 0 });
      a.venta += v.venta || 0; a.rechazo += v.rechazo || 0; a.cambio += v.cambio || 0;
    });
  });
  var out = (baseList || []).map(function (b) {
    var a = agg[b.cod] || { venta: 0, rechazo: 0, cambio: 0 };
    return {
      vendedor: b.vendedor, objetivo: b.objetivo, venta: a.venta, rechazo: a.rechazo, cambio: a.cambio,
      pct_cumplimiento: b.objetivo ? (a.venta / b.objetivo * 100) : 0,
    };
  });
  out.sort(function (a, b) { return b.venta - a.venta; });
  return out;
}

function camProductoListExcluyendo(prodCamion, labelField, excl) {
  var agg = {};
  Object.keys(prodCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var keys = prodCamion[cam];
    Object.keys(keys).forEach(function (k) {
      var v = keys[k];
      var a = agg[k] || (agg[k] = { venta: 0, unidades: 0 });
      a.venta += v.venta || 0; a.unidades += v.unidades || 0;
    });
  });
  var out = Object.keys(agg).map(function (k) {
    var o = { venta: agg[k].venta, unidades: agg[k].unidades };
    o[labelField] = k;
    return o;
  });
  out.sort(function (a, b) { return b.venta - a.venta; });
  return out.slice(0, 60);
}

function camClientesCollapse(byCamion, excl) {
  var agg = {};
  Object.keys(byCamion || {}).forEach(function (cam) {
    if (cam === excl) return;
    var clis = byCamion[cam];
    Object.keys(clis).forEach(function (cid) {
      var v = clis[cid];
      var a = agg[cid] || (agg[cid] = { venta: 0, razon_social: v.razon_social });
      a.venta += v.venta || 0;
    });
  });
  return agg;
}

// filas actualmente mostradas en cada tabla de la pestana Ventas, usadas por los botones de Excel
// para que la descarga coincida con lo que se ve en pantalla (incluida la exclusion de camion)
var VEN_TB_ACTUAL = { prov: [], chofer: [], camion: [] };

function renderVentas() {
  var d = curData();
  var camExcl = CAM_EXCL;

  var k = camExcl ? camKpisExcluyendo(d.kpis_camion, camExcl) : (d.kpis || {});
  document.getElementById('ven-kpis').innerHTML =
    KPI('Venta Neta', '$' + F(k.venta_neta), '#00e5ff') +
    KPI('Rechazado', '$' + F(k.rechazo_monto), '#ff5252') +
    KPI('Cambios', '$' + F(k.cambio_monto), '#ffab40') +
    KPI('% Rechazo', P(k.pct_rechazo), '#ff5252') +
    KPI('Comprobantes', FI(k.comprobantes), '#e3ecf7') +
    KPI('Clientes', FI(k.clientes), '#e3ecf7') +
    KPI('Choferes', FI(k.choferes), '#e3ecf7') +
    KPI('Repartos', FI(k.repartos), '#e3ecf7');

  var provSel = document.getElementById('ven-prov-f');
  var prevSel = provSel.value;
  provSel.innerHTML = '<option value="">Todos</option>' + d.provs.map(function (p) {
    return '<option value="' + p + '">' + p + '</option>';
  }).join('');
  if (d.provs.indexOf(prevSel) !== -1) provSel.value = prevSel;
  var prov = provSel.value;

  var provList = camExcl ? camProvListExcluyendo(d.prov_camion, camExcl) : d.prov;
  VEN_TB_ACTUAL.prov = provList;
  var provTb = document.getElementById('ven-prov-tb');
  provTb.innerHTML = provList.length ? provList.map(function (p) {
    return '<tr' + (p.proveedor === prov ? ' style="background:#0f1a2a"' : '') + '><td>' + p.proveedor + '</td><td>$' + F(p.venta) + '</td><td>$' + F(p.rechazo) + '</td>' +
      '<td><span class="' + pctClass(p.pct_rechazo) + '">' + P(p.pct_rechazo) + '</span></td>' +
      '<td>$' + F(p.cambio) + '</td><td><span class="' + pctClass(p.pct_cambio) + '">' + P(p.pct_cambio) + '</span></td>' +
      '<td>' + FI(p.unidades) + '</td></tr>';
  }).join('') : '<tr><td colspan="7" class="empty">Sin datos en el período</td></tr>';

  var chofer;
  if (camExcl) {
    chofer = prov
      ? camChoferListExcluyendo((d.chofer_prov_camion || {})[prov] || {}, camExcl)
      : camChoferListExcluyendo(d.chofer_camion, camExcl);
  } else {
    chofer = prov ? (d.chofer_prov[prov] || []) : d.chofer;
  }
  VEN_TB_ACTUAL.chofer = chofer;
  document.getElementById('ven-ch-titulo').textContent = prov ? ('— ' + prov) : '';
  var chTb = document.getElementById('ven-ch-tb');
  chTb.innerHTML = chofer.length ? chofer.map(function (c) {
    return '<tr><td>' + c.chofer + '</td><td>$' + F(c.venta) + '</td><td>$' + F(c.rechazo) + '</td>' +
      '<td><span class="' + pctClass(c.pct_rechazo) + '">' + P(c.pct_rechazo) + '</span></td>' +
      '<td>$' + F(c.cambio) + '</td><td><span class="' + pctClass(c.pct_cambio) + '">' + P(c.pct_cambio) + '</span></td>' +
      '<td><div class="pw"><div class="pb"><div class="pf" style="width:' + c.efectividad + '%;background:#00e5ff"></div></div>' + P(c.efectividad) + '</div></td></tr>';
  }).join('') : '<tr><td colspan="7" class="empty">Sin datos en el período</td></tr>';

  // tabla Ventas por Camion: lista todos menos el excluido (ya no filtra a "solo este")
  var camiones = camExcl ? d.camion.filter(function (c) { return c.camion !== camExcl; }) : d.camion;
  VEN_TB_ACTUAL.camion = camiones;
  var camTb = document.getElementById('ven-cam-tb');
  camTb.innerHTML = camiones.length ? camiones.map(function (c) {
    return '<tr><td>' + c.camion + '</td><td>$' + F(c.venta) + '</td><td>$' + F(c.rechazo) + '</td>' +
      '<td><span class="' + pctClass(c.pct_rechazo) + '">' + P(c.pct_rechazo) + '</span></td>' +
      '<td>$' + F(c.cambio) + '</td><td><span class="' + pctClass(c.pct_cambio) + '">' + P(c.pct_cambio) + '</span></td>' +
      '<td><div class="pw"><div class="pb"><div class="pf" style="width:' + c.efectividad + '%;background:#00e5ff"></div></div>' + P(c.efectividad) + '</div></td></tr>';
  }).join('') : '<tr><td colspan="7" class="empty">Sin datos en el período</td></tr>';
}

// ---------- HOJA DE RUTA ----------
var RUTA_SEL = null;
function initRuta() {
  var d = curData();
  var chSel = document.getElementById('ruta-ch');
  chSel.innerHTML = '<option value="">Todos</option>';
  d.chs.forEach(function (c) { chSel.innerHTML += '<option value="' + c + '">' + c + '</option>'; });
  filtRuta();
}
function filtRuta() {
  var d = curData();
  var ch = document.getElementById('ruta-ch').value;
  var q = (document.getElementById('ruta-q').value || '').toLowerCase();
  var list = d.routes.filter(function (r) { return !ch || r.chofer === ch; });
  if (CAM_EXCL) list = list.filter(function (r) { return r.vehiculo !== CAM_EXCL; });
  if (q) {
    list = list.filter(function (r) {
      var clientes = d.cli[String(r.reparto_id)] || [];
      return clientes.some(function (c) {
        return (String(c[1]) + ' ' + String(c[2])).toLowerCase().indexOf(q) !== -1;
      });
    });
  }
  var wrap = document.getElementById('rsl');
  if (!list.length) {
    wrap.innerHTML = '<div class="empty">Sin repartos en el período</div>';
    return;
  }
  wrap.innerHTML = list.map(function (r) {
    return '<div class="ri' + (RUTA_SEL === r.reparto_id ? ' on' : '') + '" onclick="selRuta(' + r.reparto_id + ')">' +
      '<div class="ri-top"><span class="ri-ch">' + r.chofer + '</span><span class="ri-rep">Rep. ' + (r.reparto_codigo || r.reparto_id) + '</span></div>' +
      '<div class="ri-meta"><span>' + (r.fecha || '') + '</span><span>' + r.vehiculo + '</span><span>$' + F(r.total) + '</span>' +
      '<span class="' + pctClass(r.pct_rechazo) + '">' + P(r.pct_rechazo) + '</span></div></div>';
  }).join('');
  if (RUTA_SEL && list.some(function (r) { return r.reparto_id === RUTA_SEL; })) selRuta(RUTA_SEL);
}
function selRuta(id) {
  var d = curData();
  RUTA_SEL = id;
  filtRuta();
  var route = d.routes.find(function (r) { return r.reparto_id === id; });
  var clientes = d.cli[String(id)] || [];
  var det = document.getElementById('rdet');
  if (!route) { det.innerHTML = '<div style="color:#5c7ba8;padding:20px">Seleccion&aacute; un reparto</div>'; return; }
  var provRows = (route.top_prov || []).map(function (p) {
    return '<span class="bp">' + p.proveedor + ': $' + F(p.importe) + '</span>';
  }).join(' ');
  det.innerHTML = '<h3 style="margin-bottom:10px;color:#00e5ff">' + route.chofer + ' &mdash; Reparto ' + (route.reparto_codigo || route.reparto_id) + '</h3>' +
    '<div style="margin-bottom:14px">' + provRows + '</div>' +
    clientes.map(function (c) {
      var flag = c[6];
      var badge = flag === 1 ? '<span class="br">Rechazado</span>' : flag === 3 ? '<span class="by">Cambio</span>' : '<span class="bg">OK</span>';
      return '<div class="cli-row"><div><div class="cli-name">' + (c[1] || '') + '</div>' +
        '<div class="cli-addr">' + (c[2] || '') + (c[3] ? ' &middot; ' + c[3] : '') + '</div>' +
        '<div class="cli-meta">' + badge + '</div></div>' +
        '<div class="cli-right">$' + F(c[5]) + '<br><span style="color:#5c7ba8">Comp. ' + (c[4] || '') + '</span></div></div>';
    }).join('');
}

// ---------- RECHAZOS ----------
var REJ_ACTUAL = { prov: [], motivo: [] };
function renderRechazos() {
  var d = curData();
  var camExcl = CAM_EXCL;
  var k = camExcl ? camKpisExcluyendo(d.kpis_camion, camExcl) : (d.kpis || {});
  document.getElementById('rej-kpis').innerHTML =
    KPI('Rechazado', '$' + F(k.rechazo_monto), '#ff5252') +
    KPI('% Rechazo', P(k.pct_rechazo), '#ff5252') +
    KPI('Comprobantes rechazados', FI(k.rechazados), '#ff5252') +
    KPI('Cambios', '$' + F(k.cambio_monto), '#ffab40') +
    KPI('% Cambio', P(k.pct_cambio), '#ffab40') +
    KPI('Comprobantes con cambio', FI(k.cambios_cant), '#ffab40');

  var provSel = document.getElementById('rej-prov-f');
  var prevSel = provSel.value;
  provSel.innerHTML = '<option value="">Todos</option>' + d.provs.map(function (p) {
    return '<option value="' + p + '">' + p + '</option>';
  }).join('');
  if (d.provs.indexOf(prevSel) !== -1) provSel.value = prevSel;
  var prov = provSel.value;

  var provList = camExcl ? camProvListExcluyendo(d.prov_camion, camExcl) : d.prov;
  REJ_ACTUAL.prov = provList;
  var provTb = document.getElementById('rej-prov-tb');
  provTb.innerHTML = provList.length ? provList.map(function (p) {
    return '<tr><td>' + p.proveedor + '</td><td>$' + F(p.rechazo) + '</td>' +
      '<td><span class="' + pctClass(p.pct_rechazo) + '">' + P(p.pct_rechazo) + '</span></td>' +
      '<td>$' + F(p.cambio) + '</td><td><span class="' + pctClass(p.pct_cambio) + '">' + P(p.pct_cambio) + '</span></td></tr>';
  }).join('') : '<tr><td colspan="5" class="empty">Sin datos en el período</td></tr>';

  var motivo;
  if (camExcl) {
    motivo = prov ? camMotivoListExcluyendo((d.motivo_prov_camion || {})[prov] || {}, camExcl)
                  : camMotivoListExcluyendo(d.motivo_camion, camExcl);
  } else {
    motivo = prov ? (d.motivo_prov[prov] || []) : d.motivo;
  }
  REJ_ACTUAL.motivo = motivo;
  var motTb = document.getElementById('rej-mot-tb');
  motTb.innerHTML = motivo.length ? motivo.map(function (m) {
    return '<tr><td>' + m.motivo + '</td><td>' + FI(m.cantidad) + '</td><td>$' + F(m.importe) + '</td><td>' + P(m.pct) + '</td></tr>';
  }).join('') : '<tr><td colspan="4" class="empty">Sin rechazos en el período</td></tr>';

  var choferBase;
  if (camExcl) {
    choferBase = prov
      ? camChoferListExcluyendo((d.chofer_prov_camion || {})[prov] || {}, camExcl)
      : camChoferListExcluyendo(d.chofer_camion, camExcl);
  } else {
    choferBase = prov ? (d.chofer_prov[prov] || []) : d.chofer;
  }
  var chList = choferBase.filter(function (c) { return c.rechazo > 0; }).sort(function (a, b) { return b.rechazo - a.rechazo; });
  var chTb = document.getElementById('rej-ch-tb');
  chTb.innerHTML = chList.length ? chList.map(function (c) {
    return '<tr><td>' + c.chofer + '</td><td>' + FI(c.rechazos || '') + '</td><td>$' + F(c.rechazo) + '</td>' +
      '<td><span class="' + pctClass(c.pct_rechazo) + '">' + P(c.pct_rechazo) + '</span></td></tr>';
  }).join('') : '<tr><td colspan="4" class="empty">Sin rechazos en el período</td></tr>';
}

// ---------- RENTABILIDAD ----------
function rentRow(a) {
  return '<tr><td>' + a.grupo + '</td><td>$' + F(a.venta) + '</td><td>$' + F(a.costo) + '</td>' +
    '<td>$' + F(a.rentabilidad) + '</td><td><span class="' + (a.pct_rentabilidad < 0 ? 'br' : (a.pct_rentabilidad < 10 ? 'by' : 'bg')) + '">' + P(a.pct_rentabilidad) + '</span></td></tr>';
}
var RENT_ACTUAL = { prov: [], chofer: [] };
function renderRentabilidad() {
  var d = curData();
  var camExcl = CAM_EXCL;
  var rentProv = camExcl ? camRentListExcluyendo(d.rent_prov_camion, camExcl) : d.rent_prov;
  var rentChofer = camExcl ? camRentListExcluyendo(d.rent_chofer_camion, camExcl) : d.rent_chofer;
  RENT_ACTUAL.prov = rentProv; RENT_ACTUAL.chofer = rentChofer;
  var totVenta = rentProv.reduce(function (s, a) { return s + a.venta; }, 0);
  var totCosto = rentProv.reduce(function (s, a) { return s + a.costo; }, 0);
  var totRent = totVenta - totCosto;
  document.getElementById('rent-kpis').innerHTML =
    KPI('Venta', '$' + F(totVenta), '#00e5ff') +
    KPI('Costo', '$' + F(totCosto), '#ffab40') +
    KPI('Rentabilidad', '$' + F(totRent), totRent >= 0 ? '#69f0ae' : '#ff5252') +
    KPI('% Rentabilidad', P(totVenta ? totRent / totVenta * 100 : 0), totRent >= 0 ? '#69f0ae' : '#ff5252');

  document.getElementById('rent-prov-tb').innerHTML = rentProv.length
    ? rentProv.map(rentRow).join('') : '<tr><td colspan="5" class="empty">Sin datos en el período</td></tr>';
  document.getElementById('rent-ch-tb').innerHTML = rentChofer.length
    ? rentChofer.map(rentRow).join('') : '<tr><td colspan="5" class="empty">Sin datos en el período</td></tr>';
}

// ---------- DESCUENTOS ----------
function descRow(a) {
  return '<tr><td>' + a.grupo + '</td><td>$' + F(a.venta_sin_desc) + '</td><td>$' + F(a.descuento) + '</td>' +
    '<td><span class="' + pctClass(a.pct_descuento) + '">' + P(a.pct_descuento) + '</span></td></tr>';
}
var DESC_ACTUAL = { prov: [], chofer: [] };
function renderDescuentos() {
  var d = curData();
  var camExcl = CAM_EXCL;
  var descProv = camExcl ? camDescListExcluyendo(d.desc_prov_camion, camExcl) : d.desc_prov;
  var descChofer = camExcl ? camDescListExcluyendo(d.desc_chofer_camion, camExcl) : d.desc_chofer;
  DESC_ACTUAL.prov = descProv; DESC_ACTUAL.chofer = descChofer;
  var totDesc = descProv.reduce(function (s, a) { return s + a.descuento; }, 0);
  var totSinDesc = descProv.reduce(function (s, a) { return s + a.venta_sin_desc; }, 0);
  document.getElementById('desc-kpis').innerHTML =
    KPI('Venta sin Dto.', '$' + F(totSinDesc), '#e3ecf7') +
    KPI('Descuento', '$' + F(totDesc), '#ffab40') +
    KPI('% Descuento', P(totSinDesc ? totDesc / totSinDesc * 100 : 0), '#ffab40');

  document.getElementById('desc-prov-tb').innerHTML = descProv.length
    ? descProv.map(descRow).join('') : '<tr><td colspan="4" class="empty">Sin datos en el período</td></tr>';
  document.getElementById('desc-ch-tb').innerHTML = descChofer.length
    ? descChofer.map(descRow).join('') : '<tr><td colspan="4" class="empty">Sin datos en el período</td></tr>';
}

// ---------- GEOGRAFIA ----------
var GEO_ACTUAL = [];
function renderGeografia() {
  var d = curData();
  var geo = CAM_EXCL ? camGeoListExcluyendo(d.geo_camion, CAM_EXCL) : d.geo;
  GEO_ACTUAL = geo;
  document.getElementById('geo-tb').innerHTML = geo.length ? geo.map(function (g) {
    return '<tr><td>' + g.localidad + '</td><td>$' + F(g.venta) + '</td><td>$' + F(g.rechazo) + '</td>' +
      '<td><span class="' + pctClass(g.pct_rechazo) + '">' + P(g.pct_rechazo) + '</span></td>' +
      '<td>$' + F(g.cambio) + '</td><td>' + FI(g.clientes) + '</td></tr>';
  }).join('') : '<tr><td colspan="6" class="empty">Sin datos en el período</td></tr>';
}

// ---------- OBJETIVO DEL MES ----------
var OBJ_ACTUAL = [];
function renderObjetivo() {
  var d = curData();
  var vendedor = CAM_EXCL ? camVendedorListExcluyendo(d.vendedor_camion, d.vendedor, CAM_EXCL) : d.vendedor;
  OBJ_ACTUAL = vendedor;
  var totObj = vendedor.reduce(function (s, a) { return s + a.objetivo; }, 0);
  var totVenta = vendedor.reduce(function (s, a) { return s + a.venta; }, 0);
  document.getElementById('obj-kpis').innerHTML =
    KPI('Objetivo', '$' + F(totObj), '#e3ecf7') +
    KPI('Venta', '$' + F(totVenta), '#00e5ff') +
    KPI('% Cumplimiento', P(totObj ? totVenta / totObj * 100 : 0), totVenta >= totObj ? '#69f0ae' : '#ffab40');

  document.getElementById('obj-tb').innerHTML = vendedor.length ? vendedor.map(function (v) {
    return '<tr><td>' + v.vendedor + '</td><td>$' + F(v.objetivo) + '</td><td>$' + F(v.venta) + '</td>' +
      '<td><div class="pw"><div class="pb"><div class="pf" style="width:' + Math.min(v.pct_cumplimiento, 100) + '%;background:' + (v.pct_cumplimiento >= 100 ? '#69f0ae' : '#ffab40') + '"></div></div>' + P(v.pct_cumplimiento) + '</div></td>' +
      '<td>$' + F(v.rechazo) + '</td><td>$' + F(v.cambio) + '</td></tr>';
  }).join('') : '<tr><td colspan="6" class="empty">Sin objetivo cargado para este período</td></tr>';
}

// ---------- EVOLUCION MENSUAL ----------
var EVO_ACTUAL = [];
function evoFilaExcluyendo(e) {
  var camData = (D_EVOLUCION_CAMION || {})[e.mes];
  if (!camData) return e;
  var k = camKpisExcluyendo(camData.kpis, CAM_EXCL);
  var rentAgg = { venta: 0, costo: 0 };
  Object.keys(camData.rent || {}).forEach(function (cam) {
    if (cam === CAM_EXCL) return;
    rentAgg.venta += camData.rent[cam].venta || 0;
    rentAgg.costo += camData.rent[cam].costo || 0;
  });
  var rentabilidad = rentAgg.venta - rentAgg.costo;
  return {
    mes: e.mes, mes_label: e.mes_label,
    venta: k.venta_neta, rechazo: k.rechazo_monto, pct_rechazo: k.pct_rechazo,
    rentabilidad: rentabilidad, pct_rentabilidad: rentAgg.venta ? (rentabilidad / rentAgg.venta * 100) : 0,
  };
}
function renderEvolucion() {
  var rows = CAM_EXCL ? D_EVOLUCION.map(evoFilaExcluyendo) : D_EVOLUCION;
  EVO_ACTUAL = rows;
  document.getElementById('evo-tb').innerHTML = rows.length ? rows.map(function (e) {
    return '<tr><td>' + e.mes_label + '</td><td>$' + F(e.venta) + '</td><td>$' + F(e.rechazo) + '</td>' +
      '<td><span class="' + pctClass(e.pct_rechazo) + '">' + P(e.pct_rechazo) + '</span></td>' +
      '<td>$' + F(e.rentabilidad) + '</td><td>' + P(e.pct_rentabilidad) + '</td></tr>';
  }).join('') : '<tr><td colspan="6" class="empty">Sin datos</td></tr>';
}

// ---------- EVOLUCION INTERANUAL ----------
function interVarCls(v) { return (v === null || v === undefined) ? '' : (v < 0 ? 'br' : (v > 0 ? 'bg' : 'by')); }
function interVarTxt(v) { return (v === null || v === undefined) ? 's/d' : ((v >= 0 ? '+' : '') + v.toFixed(1) + '%'); }
function interFila(r) {
  return '<tr><td>' + r.proveedor + '</td>' +
    '<td>' + FI(r.unidades_actual) + '</td><td>' + FI(r.unidades_anterior) + '</td>' +
    '<td><span class="' + interVarCls(r.var_unidades) + '">' + interVarTxt(r.var_unidades) + '</span></td>' +
    '<td>' + FI(r.peso_actual) + '</td><td>' + FI(r.peso_anterior) + '</td>' +
    '<td><span class="' + interVarCls(r.var_peso) + '">' + interVarTxt(r.var_peso) + '</span></td>' +
    '<td>$' + F(r.venta_actual) + '</td><td>$' + F(r.venta_anterior) + '</td>' +
    '<td><span class="' + interVarCls(r.var_venta) + '">' + interVarTxt(r.var_venta) + '</span></td></tr>';
}
function interRenderTabla(tbId, periodoElId, rows, total, periodo) {
  document.getElementById(periodoElId).textContent =
    (periodo && periodo.actual) ? ('(' + periodo.actual + ' vs ' + periodo.anterior + ')') : '';
  var html = (rows && rows.length) ? rows.map(interFila).join('') : '<tr><td colspan="10" class="empty">Sin datos</td></tr>';
  if (rows && rows.length && total) {
    html += interFila(total).replace('<tr>', '<tr style="font-weight:700;border-top:2px solid #1c2e47">');
  }
  document.getElementById(tbId).innerHTML = html;
}
// recombina unidades/peso/venta por proveedor de ambos periodos (actual y anterior) excluyendo
// un camion, y arma tanto las filas como el total, con el mismo shape que D_INTERANUAL(_MES).
function camInteranualExcluyendo(camActual, camAnterior, excl) {
  function collapse(byCamion) {
    var agg = {};
    Object.keys(byCamion || {}).forEach(function (cam) {
      if (cam === excl) return;
      var provs = byCamion[cam];
      Object.keys(provs).forEach(function (p) {
        var v = provs[p];
        var a = agg[p] || (agg[p] = { unidades: 0, peso_kg: 0, venta: 0 });
        a.unidades += v.unidades || 0; a.peso_kg += v.peso_kg || 0; a.venta += v.venta || 0;
      });
    });
    return agg;
  }
  function pct(n, o) { return o ? ((n - o) / o * 100) : null; }
  var actual = collapse(camActual), anterior = collapse(camAnterior);
  var provs = {};
  Object.keys(actual).forEach(function (p) { provs[p] = 1; });
  Object.keys(anterior).forEach(function (p) { provs[p] = 1; });
  var vacio = { unidades: 0, peso_kg: 0, venta: 0 };
  var out = Object.keys(provs).map(function (p) {
    var a = actual[p] || vacio, o = anterior[p] || vacio;
    return {
      proveedor: p,
      unidades_actual: a.unidades, unidades_anterior: o.unidades, var_unidades: pct(a.unidades, o.unidades),
      peso_actual: a.peso_kg, peso_anterior: o.peso_kg, var_peso: pct(a.peso_kg, o.peso_kg),
      venta_actual: a.venta, venta_anterior: o.venta, var_venta: pct(a.venta, o.venta),
    };
  });
  out.sort(function (x, y) { return y.venta_actual - x.venta_actual; });
  var tot1 = { unidades: 0, peso_kg: 0, venta: 0 }, tot0 = { unidades: 0, peso_kg: 0, venta: 0 };
  Object.keys(actual).forEach(function (p) { tot1.unidades += actual[p].unidades; tot1.peso_kg += actual[p].peso_kg; tot1.venta += actual[p].venta; });
  Object.keys(anterior).forEach(function (p) { tot0.unidades += anterior[p].unidades; tot0.peso_kg += anterior[p].peso_kg; tot0.venta += anterior[p].venta; });
  var total = {
    proveedor: 'TOTAL',
    unidades_actual: tot1.unidades, unidades_anterior: tot0.unidades, var_unidades: pct(tot1.unidades, tot0.unidades),
    peso_actual: tot1.peso_kg, peso_anterior: tot0.peso_kg, var_peso: pct(tot1.peso_kg, tot0.peso_kg),
    venta_actual: tot1.venta, venta_anterior: tot0.venta, var_venta: pct(tot1.venta, tot0.venta),
  };
  return { rows: out, total: total };
}
var INTER_ACTUAL = { mes: [], anio: [] };
function renderInteranual() {
  if (CAM_EXCL) {
    var mesR = camInteranualExcluyendo(D_INTERANUAL_MES_CAMION_ACTUAL, D_INTERANUAL_MES_CAMION_ANTERIOR, CAM_EXCL);
    interRenderTabla('inter-mes-tb', 'inter-mes-periodo', mesR.rows, mesR.total, D_INTERANUAL_MES_PERIODO);
    INTER_ACTUAL.mes = mesR.rows.concat([mesR.total]);
    var anioR = camInteranualExcluyendo(D_INTERANUAL_CAMION_ACTUAL, D_INTERANUAL_CAMION_ANTERIOR, CAM_EXCL);
    interRenderTabla('inter-tb', 'inter-periodo', anioR.rows, anioR.total, D_INTERANUAL_PERIODO);
    INTER_ACTUAL.anio = anioR.rows.concat([anioR.total]);
  } else {
    interRenderTabla('inter-mes-tb', 'inter-mes-periodo', D_INTERANUAL_MES, D_INTERANUAL_MES_TOTAL, D_INTERANUAL_MES_PERIODO);
    INTER_ACTUAL.mes = (D_INTERANUAL_MES || []).concat(D_INTERANUAL_MES_TOTAL ? [D_INTERANUAL_MES_TOTAL] : []);
    interRenderTabla('inter-tb', 'inter-periodo', D_INTERANUAL, D_INTERANUAL_TOTAL, D_INTERANUAL_PERIODO);
    INTER_ACTUAL.anio = (D_INTERANUAL || []).concat(D_INTERANUAL_TOTAL ? [D_INTERANUAL_TOTAL] : []);
  }
}
function dlInteranual() { dl(INTER_ACTUAL.anio, 'pyp_evolucion_interanual_acumulado.xlsx'); }
function dlInteranualMes() { dl(INTER_ACTUAL.mes, 'pyp_evolucion_interanual_mes.xlsx'); }

// ---------- NO COMPRADORES ----------
function diasClass(d) {
  if (d >= 180) return 'br';
  if (d >= 90) return 'by';
  return 'bg';
}
// recalcula ultima compra por cliente-proveedor excluyendo un camion: toma el maximo entre
// los camiones restantes y vuelve a aplicar la ventana de 15-365 dias (igual que Python).
function camNoCompradoresExcluyendo(excl) {
  var agg = {};
  Object.keys(D_NO_COMPRADORES_CAMION || {}).forEach(function (cam) {
    if (cam === excl) return;
    var keys = D_NO_COMPRADORES_CAMION[cam];
    Object.keys(keys).forEach(function (key) {
      var v = keys[key];
      var a = agg[key];
      if (!a || v.ultima_compra > a.ultima_compra) agg[key] = v;
    });
  });
  var hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  var out = [];
  Object.keys(agg).forEach(function (key) {
    var v = agg[key];
    var fecha = new Date(v.ultima_compra + 'T00:00:00');
    var dias = Math.round((hoy - fecha) / 86400000);
    if (dias < 15 || dias > 365) return;
    out.push({
      cliente_id: v.cliente_id, razon_social: v.razon_social, proveedor: v.proveedor,
      ultima_compra: v.ultima_compra, dias_sin_comprar: dias,
    });
  });
  out.sort(function (a, b) { return b.dias_sin_comprar - a.dias_sin_comprar; });
  return out;
}
var NOC_FILTRADOS = [];
function renderNoCompradores() {
  var todos = CAM_EXCL ? camNoCompradoresExcluyendo(CAM_EXCL) : (D_NO_COMPRADORES || []);
  var provs = [];
  todos.forEach(function (r) { if (provs.indexOf(r.proveedor) === -1) provs.push(r.proveedor); });
  provs.sort();

  var provSel = document.getElementById('noc-prov-f');
  var prevSel = provSel.value;
  provSel.innerHTML = '<option value="">Todos</option>' + provs.map(function (p) {
    return '<option value="' + p + '">' + p + '</option>';
  }).join('');
  if (provs.indexOf(prevSel) !== -1) provSel.value = prevSel;
  var prov = provSel.value;

  var rows = prov ? todos.filter(function (r) { return r.proveedor === prov; }) : todos;
  NOC_FILTRADOS = rows;
  var tb = document.getElementById('noc-tb');
  tb.innerHTML = rows.length ? rows.map(function (r) {
    return '<tr><td>' + (r.razon_social || r.cliente_id) + '</td><td>' + r.proveedor + '</td>' +
      '<td>' + r.ultima_compra + '</td>' +
      '<td><span class="' + diasClass(r.dias_sin_comprar) + '">' + FI(r.dias_sin_comprar) + '</span></td></tr>';
  }).join('') : '<tr><td colspan="4" class="empty">Sin datos</td></tr>';
}
function dlNoCompradores() { dl(NOC_FILTRADOS, 'pyp_no_compradores.xlsx'); }

// ---------- CLIENTES (tendencia) ----------
function camClientesTendenciaExcluyendo(d, excl) {
  var actual = camClientesCollapse(d.clientes_camion, excl);
  var anterior = camClientesCollapse(d.clientes_camion_anterior, excl);
  var out = Object.keys(actual).map(function (cid) {
    var a = actual[cid], ventaAnt = (anterior[cid] || {}).venta || 0;
    var variacion = a.venta - ventaAnt;
    return {
      cliente_id: cid, razon_social: a.razon_social, venta: a.venta, venta_mes_anterior: ventaAnt,
      variacion: variacion, pct_variacion: ventaAnt ? (variacion / ventaAnt * 100) : 0,
    };
  });
  out.sort(function (a, b) { return a.variacion - b.variacion; });
  return out.slice(0, 60);
}
var CLI_TEND_ACTUAL = [];
function renderClientes() {
  var d = curData();
  var clientes = CAM_EXCL ? camClientesTendenciaExcluyendo(d, CAM_EXCL) : d.clientes;
  CLI_TEND_ACTUAL = clientes;
  document.getElementById('cli-tend-tb').innerHTML = clientes.length ? clientes.map(function (c) {
    var cls = c.variacion < 0 ? 'br' : (c.variacion > 0 ? 'bg' : 'by');
    return '<tr><td>' + (c.razon_social || c.cliente_id) + '</td><td>$' + F(c.venta) + '</td><td>$' + F(c.venta_mes_anterior) + '</td>' +
      '<td><span class="' + cls + '">$' + F(c.variacion) + '</span></td><td>' + P(c.pct_variacion) + '</td></tr>';
  }).join('') : '<tr><td colspan="5" class="empty">Sin datos comparables (falta mes anterior)</td></tr>';
}

// ---------- POR PRODUCTO ----------
var PROD_ACTUAL = { producto: [], rubro: [] };
function renderProducto() {
  var d = curData();
  var camExcl = CAM_EXCL;
  var producto = camExcl ? camProductoListExcluyendo(d.producto_camion, 'producto', camExcl) : d.producto;
  var rubro = camExcl ? camProductoListExcluyendo(d.rubro_camion, 'rubro', camExcl) : d.rubro;
  PROD_ACTUAL.producto = producto; PROD_ACTUAL.rubro = rubro;
  document.getElementById('prod-tb').innerHTML = producto.length ? producto.map(function (p) {
    return '<tr><td>' + p.producto + '</td><td>$' + F(p.venta) + '</td><td>' + FI(p.unidades) + '</td></tr>';
  }).join('') : '<tr><td colspan="3" class="empty">Sin datos en el período</td></tr>';
  document.getElementById('rubro-tb').innerHTML = rubro.length ? rubro.map(function (r) {
    return '<tr><td>' + r.rubro + '</td><td>$' + F(r.venta) + '</td><td>' + FI(r.unidades) + '</td></tr>';
  }).join('') : '<tr><td colspan="3" class="empty">Sin datos en el período</td></tr>';
}

// ---------- EXPORT EXCEL ----------
function dl(rows, filename) {
  var ws = XLSX.utils.json_to_sheet(rows);
  var wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Datos');
  XLSX.writeFile(wb, filename);
}
function dlProv() { dl(VEN_TB_ACTUAL.prov, 'pyp_ventas_por_proveedor_' + MES_ACTIVO + '.xlsx'); }
function dlChofer() {
  var prov = document.getElementById('ven-prov-f').value;
  dl(VEN_TB_ACTUAL.chofer, 'pyp_ventas_por_chofer_' + (prov ? prov.replace(/[^a-z0-9]+/gi, '_') + '_' : '') + MES_ACTIVO + '.xlsx');
}
function dlMotivo() { dl(REJ_ACTUAL.motivo, 'pyp_rechazos_por_motivo_' + MES_ACTIVO + '.xlsx'); }
function dlProvRech() { dl(REJ_ACTUAL.prov, 'pyp_rechazos_por_proveedor_' + MES_ACTIVO + '.xlsx'); }
function dlCamion() { dl(VEN_TB_ACTUAL.camion, 'pyp_ventas_por_camion_' + MES_ACTIVO + '.xlsx'); }
function dlRentProv() { dl(RENT_ACTUAL.prov, 'pyp_rentabilidad_por_proveedor_' + MES_ACTIVO + '.xlsx'); }
function dlRentChofer() { dl(RENT_ACTUAL.chofer, 'pyp_rentabilidad_por_chofer_' + MES_ACTIVO + '.xlsx'); }
function dlDescProv() { dl(DESC_ACTUAL.prov, 'pyp_descuentos_por_proveedor_' + MES_ACTIVO + '.xlsx'); }
function dlDescChofer() { dl(DESC_ACTUAL.chofer, 'pyp_descuentos_por_chofer_' + MES_ACTIVO + '.xlsx'); }
function dlGeo() { dl(GEO_ACTUAL, 'pyp_geografia_' + MES_ACTIVO + '.xlsx'); }
function dlObjetivo() { dl(OBJ_ACTUAL, 'pyp_objetivo_' + MES_ACTIVO + '.xlsx'); }
function dlEvolucion() { dl(EVO_ACTUAL.length ? EVO_ACTUAL : D_EVOLUCION, 'pyp_evolucion_mensual.xlsx'); }
function dlClientes() { dl(CLI_TEND_ACTUAL, 'pyp_clientes_tendencia_' + MES_ACTIVO + '.xlsx'); }
function dlProducto() { dl(PROD_ACTUAL.producto, 'pyp_por_producto_' + MES_ACTIVO + '.xlsx'); }
function dlRubro() { dl(PROD_ACTUAL.rubro, 'pyp_por_rubro_' + MES_ACTIVO + '.xlsx'); }
function dlRuta() {
  var d = curData();
  var rows = [];
  var routes = CAM_EXCL ? d.routes.filter(function (r) { return r.vehiculo !== CAM_EXCL; }) : d.routes;
  routes.forEach(function (r) {
    (d.cli[String(r.reparto_id)] || []).forEach(function (c) {
      rows.push({
        reparto: r.reparto_codigo || r.reparto_id, chofer: r.chofer, fecha: r.fecha,
        cliente_id: c[0], razon_social: c[1], direccion: c[2], localidad: c[3],
        comprobante: c[4], importe: c[5], estado: c[6] === 1 ? 'Rechazado' : (c[6] === 3 ? 'Cambio' : 'OK'),
      });
    });
  });
  dl(rows, 'pyp_hoja_de_ruta_' + MES_ACTIVO + '.xlsx');
}

// ---------- INIT / SESSION / SW ----------
window.addEventListener('load', function () {
  var saved = sessionStorage.getItem('vsb_auth');
  if (saved === 'sup') {
    ROLE = 'sup'; VEND_COD = null;
    entrar();
  } else if (saved && saved.indexOf('vendedor:') === 0) {
    ROLE = 'vendedor'; VEND_COD = saved.split(':')[1];
    entrar();
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('service-worker.js').catch(function () {});
  }
});
