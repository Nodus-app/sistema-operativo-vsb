#!/usr/bin/env python3
"""
generar_dashboard.py - VSB Distribuciones Dashboard Operativo
Consulta directo la base BI de GesCom (Postgres) y regenera index.html.
Credenciales por variables de entorno: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD, PGTENANT.
"""
import json, os, sys, math
from datetime import datetime, timedelta, timezone
import psycopg2
import psycopg2.extras

print("=" * 60)
print("VSB Distribuciones - Generador Dashboard Operativo")
print("=" * 60)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TENANT_ID = int(os.environ.get("PGTENANT", "30"))

MES_NOMBRE = {1:'Enero',2:'Febrero',3:'Marzo',4:'Abril',5:'Mayo',6:'Junio',
              7:'Julio',8:'Agosto',9:'Septiembre',10:'Octubre',11:'Noviembre',12:'Diciembre'}


def sf(v, d=0.0):
    try:
        if v is None:
            return d
        f = float(v)
        return d if math.isnan(f) else f
    except Exception:
        return d


def si(v, d=0):
    try:
        return d if v is None else int(v)
    except Exception:
        return d


def connect():
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        connect_timeout=15,
    )


MESES_HISTORIAL = int(os.environ.get("MESES_HISTORIAL", "12"))


def rango_historial():
    """Desde el primer dia del mes que quedo MESES_HISTORIAL atras, hasta hoy."""
    hoy = datetime.now(timezone.utc).replace(tzinfo=None)
    mes_inicio = hoy.month - (MESES_HISTORIAL - 1)
    anio_inicio = hoy.year + (mes_inicio - 1) // 12
    mes_inicio = (mes_inicio - 1) % 12 + 1
    desde = hoy.replace(year=anio_inicio, month=mes_inicio, day=1, hour=0, minute=0, second=0, microsecond=0)
    hasta = hoy + timedelta(days=1)
    return desde, hasta, hoy


def rango_interanual(hoy):
    """Año actual desde el 1/1 hasta hoy, y el mismo rango (mismo dia y mes) del año anterior."""
    desde_actual = hoy.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    hasta_actual = hoy + timedelta(days=1)
    desde_anterior = desde_actual.replace(year=desde_actual.year - 1)
    try:
        hasta_anterior = hoy.replace(year=hoy.year - 1) + timedelta(days=1)
    except ValueError:
        # 29 de febrero en año bisiesto: el año anterior no tiene ese dia
        hasta_anterior = hoy.replace(year=hoy.year - 1, day=28) + timedelta(days=1)
    return desde_actual, hasta_actual, desde_anterior, hasta_anterior


def rango_mes_actual_interanual(hoy):
    """Mes en curso, acumulado a hoy, vs el mismo rango de dias del mismo mes del año anterior."""
    desde_actual = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    hasta_actual = hoy + timedelta(days=1)
    desde_anterior = desde_actual.replace(year=desde_actual.year - 1)
    try:
        hasta_anterior = hoy.replace(year=hoy.year - 1) + timedelta(days=1)
    except ValueError:
        # 29 de febrero en año bisiesto: el año anterior no tiene ese dia
        hasta_anterior = hoy.replace(year=hoy.year - 1, day=28) + timedelta(days=1)
    return desde_actual, hasta_actual, desde_anterior, hasta_anterior


def mes_key(fecha):
    return f"{fecha.year:04d}-{fecha.month:02d}"


def mes_anterior(m):
    anio, mes = (int(x) for x in m.split("-"))
    if mes == 1:
        return f"{anio - 1:04d}-12"
    return f"{anio:04d}-{mes - 1:02d}"


def make_json(var_name, data):
    return f"var {var_name}={json.dumps(data, ensure_ascii=True, separators=(',', ':'), default=str)};"


# Solo documentos que representan movimiento de $ real (se excluyen remitos REME/REMI, sin importe,
# y notas de debito NDB, poco frecuentes y no ligadas a rechazos/cambios).
TIPOS_VALIDOS = ('FAC-A', 'FAC-B', 'NCR-A', 'NCR-B')


def fetch_ordenes(cur, desde, hasta):
    cur.execute(
        """
        SELECT v.id, v.reparto_id, v.reparto_codigo,
               v.empleado_chofer_id, v.empleado_chofer_nombre,
               v.vehiculo_id, v.vehiculo_codigo, v.vehiculo_descripcion,
               v.cliente_id, v.razon_social,
               ch.direccion, ch.localidad,
               v.fecha_comprobante, v.fecha_entrega, v.numero_comprobante, v.tipo_comprobante_codigo,
               v.motivo_rechazo_codigo, v.motivo_rechazo_desc,
               v.motivo_cambio_codigo, v.motivo_cambio_desc,
               v.importe_total, v.importe_neto,
               v.vendedor_codigo, v.vendedor_nombre
        FROM venta v
        LEFT JOIN cliente_hist ch ON ch.hist_id = v.cliente_hist_id AND ch.tenant_id = v.tenant_id
        WHERE v.tenant_id = %(tenant)s
          AND v.fecha_entrega >= %(desde)s AND v.fecha_entrega < %(hasta)s
          AND v.tipo_comprobante_codigo IN %(tipos)s
        ORDER BY v.fecha_entrega
        """,
        {"tenant": TENANT_ID, "desde": desde, "hasta": hasta, "tipos": TIPOS_VALIDOS},
    )
    return cur.fetchall()


def fetch_items(cur, desde, hasta):
    cur.execute(
        """
        SELECT v.id AS venta_id, v.reparto_id, v.empleado_chofer_nombre,
               v.vehiculo_codigo, v.vehiculo_descripcion,
               v.tipo_comprobante_codigo, v.motivo_cambio_codigo,
               v.motivo_rechazo_desc, v.fecha_comprobante, v.fecha_entrega,
               v.vendedor_codigo, v.vendedor_nombre,
               ch.localidad,
               i.prov_razonsocial, i.prov_codigo, i.descripcion AS item_descripcion, i.rubro_desc,
               vi.importe_total_c_imp, vi.importe_iva, vi.cantidad, vi.unidades,
               vi.precio_costo_unitario, vi.precio_unitario, vi.precio_unitario_s_desc
        FROM venta v
        JOIN venta_item vi ON vi.venta_id = v.id AND vi.tenant_id = v.tenant_id
        LEFT JOIN item i ON i.codigo = vi.item_codigo AND i.tenant_id = v.tenant_id
        LEFT JOIN cliente_hist ch ON ch.hist_id = v.cliente_hist_id AND ch.tenant_id = v.tenant_id
        WHERE v.tenant_id = %(tenant)s
          AND v.fecha_entrega >= %(desde)s AND v.fecha_entrega < %(hasta)s
          AND v.tipo_comprobante_codigo IN %(tipos)s
        """,
        {"tenant": TENANT_ID, "desde": desde, "hasta": hasta, "tipos": TIPOS_VALIDOS},
    )
    return cur.fetchall()


def fetch_objetivos(cur):
    cur.execute(
        """
        SELECT o.descripcion, od.vendedor_codigo, od.vendedor_nombre, sum(od.cantidad) AS objetivo
        FROM objetivo_detalle od
        JOIN objetivo o ON o.codigo = od.objetivo_codigo AND o.tenant_id = od.tenant_id
        WHERE od.tenant_id = %(tenant)s AND od.medida = 'Importe'
        GROUP BY o.descripcion, od.vendedor_codigo, od.vendedor_nombre
        """,
        {"tenant": TENANT_ID},
    )
    return cur.fetchall()


def fetch_venta_periodo(cur, desde, hasta):
    """Venta real (excluye rechazos/cambios/ajustes) por linea, para un rango de fechas arbitrario.
    Funciona tanto en el regimen moderno (tipo_comprobante_codigo FAC-A/FAC-B) como en el legacy
    pre-sept-2025, donde tipo_comprobante_codigo viene siempre 'Venta' y el discriminador real es
    tipo_venta='VEN' (ver PYP - Base BI Postgres.md en el vault)."""
    cur.execute(
        """
        SELECT i.prov_razonsocial, i.peso, vi.cantidad, vi.importe_total_c_imp,
               v.vehiculo_codigo, v.vehiculo_descripcion
        FROM venta v
        JOIN venta_item vi ON vi.venta_id = v.id AND vi.tenant_id = v.tenant_id
        LEFT JOIN item i ON i.codigo = vi.item_codigo AND i.tenant_id = v.tenant_id
        WHERE v.tenant_id = %(tenant)s
          AND v.fecha_entrega >= %(desde)s AND v.fecha_entrega < %(hasta)s
          AND (v.tipo_comprobante_codigo IN ('FAC-A', 'FAC-B')
               OR (v.tipo_comprobante_codigo = 'Venta' AND v.tipo_venta = 'VEN'))
        """,
        {"tenant": TENANT_ID, "desde": desde, "hasta": hasta},
    )
    return cur.fetchall()


def build_interanual_por_prov(rows_actual, rows_anterior):
    """Unidades/peso(kg)/venta($) por proveedor, año actual YTD vs mismo rango del año anterior."""
    def agg(rows):
        out = {}
        for r in rows:
            prov = r["prov_razonsocial"] or "Sin proveedor"
            a = out.setdefault(prov, {"unidades": 0.0, "peso_kg": 0.0, "venta": 0.0})
            cant = sf(r["cantidad"])
            a["unidades"] += cant
            a["peso_kg"] += cant * sf(r["peso"]) / 1000.0
            a["venta"] += abs(sf(r["importe_total_c_imp"]))
        return out

    a1 = agg(rows_actual)
    a0 = agg(rows_anterior)
    provs = sorted(set(a1) | set(a0), key=lambda p: -a1.get(p, {}).get("venta", 0.0))

    def pct(new, old):
        return round((new - old) / old * 100, 2) if old else None

    def fila(prov, d1, d0):
        return {
            "proveedor": prov,
            "unidades_actual": round(d1["unidades"]), "unidades_anterior": round(d0["unidades"]),
            "var_unidades": pct(d1["unidades"], d0["unidades"]),
            "peso_actual": round(d1["peso_kg"], 1), "peso_anterior": round(d0["peso_kg"], 1),
            "var_peso": pct(d1["peso_kg"], d0["peso_kg"]),
            "venta_actual": round(d1["venta"], 2), "venta_anterior": round(d0["venta"], 2),
            "var_venta": pct(d1["venta"], d0["venta"]),
        }

    vacio = {"unidades": 0.0, "peso_kg": 0.0, "venta": 0.0}
    out = [fila(p, a1.get(p, vacio), a0.get(p, vacio)) for p in provs]

    tot1 = {"unidades": sum(d["unidades"] for d in a1.values()),
            "peso_kg": sum(d["peso_kg"] for d in a1.values()),
            "venta": sum(d["venta"] for d in a1.values())}
    tot0 = {"unidades": sum(d["unidades"] for d in a0.values()),
            "peso_kg": sum(d["peso_kg"] for d in a0.values()),
            "venta": sum(d["venta"] for d in a0.values())}
    total = fila("TOTAL", tot1, tot0)
    return out, total


def fetch_ultima_compra(cur):
    """Ultima fecha de compra real (venta, no rechazo/cambio/ajuste) por cliente y proveedor,
    contra TODO el historico (no se limita a MESES_HISTORIAL como el resto del dashboard),
    para poder detectar clientes que dejaron de comprarle a un proveedor aunque haga mas de
    un año. Mismo criterio FAC-A/FAC-B o tipo_venta='VEN' que fetch_venta_periodo."""
    cur.execute(
        """
        SELECT v.cliente_id, v.razon_social, i.prov_razonsocial,
               v.vehiculo_codigo, v.vehiculo_descripcion,
               max(v.fecha_entrega) as ultima_compra
        FROM venta v
        JOIN venta_item vi ON vi.venta_id = v.id AND vi.tenant_id = v.tenant_id
        LEFT JOIN item i ON i.codigo = vi.item_codigo AND i.tenant_id = v.tenant_id
        WHERE v.tenant_id = %(tenant)s
          AND v.cliente_id IS NOT NULL
          AND (v.tipo_comprobante_codigo IN ('FAC-A', 'FAC-B')
               OR (v.tipo_comprobante_codigo = 'Venta' AND v.tipo_venta = 'VEN'))
        GROUP BY v.cliente_id, v.razon_social, i.prov_razonsocial, v.vehiculo_codigo, v.vehiculo_descripcion
        """,
        {"tenant": TENANT_ID},
    )
    return cur.fetchall()


def build_no_compradores(rows, hoy):
    """Dias desde la ultima compra real, por cliente y proveedor (igual criterio que la medida
    'Dias desde Ultima Compra' del Power BI corporativo: DATEDIFF(UltimaFechaDeCompra, HOY, DAY)).
    rows viene agrupado tambien por camion (para el filtro global Excluir Camion, ver
    build_no_compradores_por_camion), asi que primero hay que colapsar al maximo por
    cliente-proveedor entre todos los camiones.
    Ventana 15-365 dias: menos de 15 todavia no es una alerta (puede ser solo el ciclo normal de
    compra), mas de 365 ya esta tan inactivo que no aporta como alerta accionable de seguimiento
    comercial (son ~1150 combinaciones sobre 7950 totales, quedan fuera)."""
    colapsado = {}
    for r in rows:
        ultima = r["ultima_compra"]
        if ultima is None:
            continue
        key = (r["cliente_id"], r["prov_razonsocial"])
        a = colapsado.get(key)
        if a is None or ultima > a["ultima_compra"]:
            colapsado[key] = {"cliente_id": r["cliente_id"], "razon_social": r["razon_social"],
                               "prov_razonsocial": r["prov_razonsocial"], "ultima_compra": ultima}
    out = []
    for r in colapsado.values():
        ultima = r["ultima_compra"]
        dias = (hoy.date() - ultima.date()).days
        if dias < 15 or dias > 365:
            continue
        out.append({
            "cliente_id": r["cliente_id"],
            "razon_social": r["razon_social"] or f"Cliente {r['cliente_id']}",
            "proveedor": r["prov_razonsocial"] or "Sin proveedor",
            "ultima_compra": ultima.strftime("%Y-%m-%d"),
            "dias_sin_comprar": dias,
        })
    out.sort(key=lambda r: -r["dias_sin_comprar"])
    return out


def es_devolucion(row):
    return (row.get("tipo_comprobante_codigo") or "").startswith("NCR")


def es_cambio(row):
    return es_devolucion(row) and row.get("motivo_cambio_codigo") is not None


def es_rechazo_puro(row):
    return es_devolucion(row) and not es_cambio(row)


def build_kpis(ordenes):
    venta_neta = sum(sf(o["importe_total"]) for o in ordenes if not es_devolucion(o))
    rechazo = sum(sf(o["importe_total"]) for o in ordenes if es_rechazo_puro(o))
    cambio = sum(sf(o["importe_total"]) for o in ordenes if es_cambio(o))
    bruta = venta_neta + rechazo + cambio
    comprobantes = len(ordenes)
    clientes = len({o["cliente_id"] for o in ordenes if o["cliente_id"] is not None})
    choferes = len({o["empleado_chofer_id"] for o in ordenes if o["empleado_chofer_id"] is not None})
    repartos = len({o["reparto_id"] for o in ordenes if o["reparto_id"] is not None})
    rechazados = sum(1 for o in ordenes if es_rechazo_puro(o))
    cambios_cant = sum(1 for o in ordenes if es_cambio(o))
    return {
        "venta_neta": round(venta_neta, 2),
        "rechazo_monto": round(rechazo, 2),
        "cambio_monto": round(cambio, 2),
        "pct_rechazo": round((rechazo / bruta * 100) if bruta else 0, 2),
        "pct_cambio": round((cambio / bruta * 100) if bruta else 0, 2),
        "comprobantes": comprobantes,
        "rechazados": rechazados,
        "cambios_cant": cambios_cant,
        "clientes": clientes,
        "choferes": choferes,
        "repartos": repartos,
    }


def build_prov(items):
    agg = {}
    for it in items:
        prov = it["prov_razonsocial"] or "Sin proveedor"
        a = agg.setdefault(prov, {"proveedor": prov, "venta": 0.0, "rechazo": 0.0, "cambio": 0.0, "unidades": 0})
        # a nivel de linea el signo no es confiable (puede venir negativo tanto en
        # facturas como en notas de credito); el total de cabecera si es siempre positivo.
        monto = abs(sf(it["importe_total_c_imp"]))
        if es_rechazo_puro(it):
            a["rechazo"] += monto
        elif es_cambio(it):
            a["cambio"] += monto
        elif not es_devolucion(it):
            a["venta"] += monto
        a["unidades"] += si(sf(it["cantidad"]))
    out = list(agg.values())
    for a in out:
        bruta = a["venta"] + a["rechazo"] + a["cambio"]
        a["pct_rechazo"] = round((a["rechazo"] / bruta * 100) if bruta else 0, 2)
        a["pct_cambio"] = round((a["cambio"] / bruta * 100) if bruta else 0, 2)
        a["venta"] = round(a["venta"], 2)
        a["rechazo"] = round(a["rechazo"], 2)
        a["cambio"] = round(a["cambio"], 2)
    out.sort(key=lambda a: -a["venta"])
    return out


def build_chofer(ordenes):
    agg = {}
    for o in ordenes:
        ch = o["empleado_chofer_nombre"] or "Sin asignar"
        a = agg.setdefault(ch, {"chofer": ch, "venta": 0.0, "rechazo": 0.0, "cambio": 0.0, "entregas": 0, "rechazos": 0, "cambios": 0})
        monto = sf(o["importe_total"])
        if es_rechazo_puro(o):
            a["rechazo"] += monto
            a["rechazos"] += 1
        elif es_cambio(o):
            a["cambio"] += monto
            a["cambios"] += 1
        elif not es_devolucion(o):
            a["venta"] += monto
            a["entregas"] += 1
    out = list(agg.values())
    for a in out:
        total = a["entregas"] + a["rechazos"] + a["cambios"]
        bruta = a["venta"] + a["rechazo"] + a["cambio"]
        a["pct_rechazo"] = round((a["rechazo"] / bruta * 100) if bruta else 0, 2)
        a["pct_cambio"] = round((a["cambio"] / bruta * 100) if bruta else 0, 2)
        a["efectividad"] = round((a["entregas"] / total * 100) if total else 0, 2)
        a["venta"] = round(a["venta"], 2)
        a["rechazo"] = round(a["rechazo"], 2)
        a["cambio"] = round(a["cambio"], 2)
    out.sort(key=lambda a: -a["venta"])
    return out


def build_camion(ordenes):
    agg = {}
    for o in ordenes:
        cam = _camion_label(o)
        a = agg.setdefault(cam, {"camion": cam, "venta": 0.0, "rechazo": 0.0, "cambio": 0.0, "entregas": 0, "rechazos": 0, "cambios": 0})
        monto = sf(o["importe_total"])
        if es_rechazo_puro(o):
            a["rechazo"] += monto
            a["rechazos"] += 1
        elif es_cambio(o):
            a["cambio"] += monto
            a["cambios"] += 1
        elif not es_devolucion(o):
            a["venta"] += monto
            a["entregas"] += 1
    out = list(agg.values())
    for a in out:
        total = a["entregas"] + a["rechazos"] + a["cambios"]
        bruta = a["venta"] + a["rechazo"] + a["cambio"]
        a["pct_rechazo"] = round((a["rechazo"] / bruta * 100) if bruta else 0, 2)
        a["pct_cambio"] = round((a["cambio"] / bruta * 100) if bruta else 0, 2)
        a["efectividad"] = round((a["entregas"] / total * 100) if total else 0, 2)
        a["venta"] = round(a["venta"], 2)
        a["rechazo"] = round(a["rechazo"], 2)
        a["cambio"] = round(a["cambio"], 2)
    out.sort(key=lambda a: -a["venta"])
    return out


def _camion_label(row):
    return row["vehiculo_descripcion"] or row["vehiculo_codigo"] or "Sin asignar"


def build_kpis_por_camion(ordenes):
    """Contribucion de cada camion a los KPIs globales, para poder recalcular
    'todos menos este camion' en el frontend (filtro Excluir Camion).
    clientes/choferes/repartos van como listas de ids (no como conteo) porque son
    conteos DISTINCT: un mismo cliente/chofer puede aparecer en mas de un camion en
    el mismo mes, asi que no se pueden restar, hay que rearmar el set en el cliente."""
    agg = {}
    for o in ordenes:
        cam = _camion_label(o)
        a = agg.setdefault(cam, {
            "venta_neta": 0.0, "rechazo_monto": 0.0, "cambio_monto": 0.0,
            "comprobantes": 0, "rechazados": 0, "cambios_cant": 0,
            "clientes": set(), "choferes": set(), "repartos": set(),
        })
        monto = sf(o["importe_total"])
        if es_rechazo_puro(o):
            a["rechazo_monto"] += monto
            a["rechazados"] += 1
        elif es_cambio(o):
            a["cambio_monto"] += monto
            a["cambios_cant"] += 1
        elif not es_devolucion(o):
            a["venta_neta"] += monto
        a["comprobantes"] += 1
        if o["cliente_id"] is not None:
            a["clientes"].add(o["cliente_id"])
        if o["empleado_chofer_id"] is not None:
            a["choferes"].add(o["empleado_chofer_id"])
        if o["reparto_id"] is not None:
            a["repartos"].add(o["reparto_id"])
    out = {}
    for cam, a in agg.items():
        out[cam] = {
            "venta_neta": round(a["venta_neta"], 2),
            "rechazo_monto": round(a["rechazo_monto"], 2),
            "cambio_monto": round(a["cambio_monto"], 2),
            "comprobantes": a["comprobantes"],
            "rechazados": a["rechazados"],
            "cambios_cant": a["cambios_cant"],
            "clientes": list(a["clientes"]),
            "choferes": list(a["choferes"]),
            "repartos": list(a["repartos"]),
        }
    return out


def build_prov_por_camion(items):
    """Igual que build_prov pero desglosado por camion, para el filtro Excluir Camion."""
    agg = {}
    for it in items:
        cam = _camion_label(it)
        prov = it["prov_razonsocial"] or "Sin proveedor"
        a = agg.setdefault(cam, {}).setdefault(prov, {"venta": 0.0, "rechazo": 0.0, "cambio": 0.0, "unidades": 0})
        monto = abs(sf(it["importe_total_c_imp"]))
        if es_rechazo_puro(it):
            a["rechazo"] += monto
        elif es_cambio(it):
            a["cambio"] += monto
        elif not es_devolucion(it):
            a["venta"] += monto
        a["unidades"] += si(sf(it["cantidad"]))
    out = {}
    for cam, provs in agg.items():
        out[cam] = {p: {"venta": round(v["venta"], 2), "rechazo": round(v["rechazo"], 2),
                         "cambio": round(v["cambio"], 2), "unidades": v["unidades"]}
                    for p, v in provs.items()}
    return out


def build_chofer_por_camion(ordenes):
    """Igual que build_chofer pero desglosado por camion, para el filtro Excluir Camion."""
    agg = {}
    for o in ordenes:
        cam = _camion_label(o)
        ch = o["empleado_chofer_nombre"] or "Sin asignar"
        a = agg.setdefault(cam, {}).setdefault(ch, {"venta": 0.0, "rechazo": 0.0, "cambio": 0.0,
                                                      "entregas": 0, "rechazos": 0, "cambios": 0})
        monto = sf(o["importe_total"])
        if es_rechazo_puro(o):
            a["rechazo"] += monto
            a["rechazos"] += 1
        elif es_cambio(o):
            a["cambio"] += monto
            a["cambios"] += 1
        elif not es_devolucion(o):
            a["venta"] += monto
            a["entregas"] += 1
    out = {}
    for cam, chs in agg.items():
        out[cam] = {c: {"venta": round(v["venta"], 2), "rechazo": round(v["rechazo"], 2),
                         "cambio": round(v["cambio"], 2), "entregas": v["entregas"],
                         "rechazos": v["rechazos"], "cambios": v["cambios"]}
                    for c, v in chs.items()}
    return out


def build_chofer_por_prov_por_camion(items):
    """Igual que build_chofer_por_prov pero con un nivel extra de camion, para poder
    excluir un camion aunque el usuario tambien tenga un proveedor seleccionado."""
    agg = {}
    for it in items:
        prov = it["prov_razonsocial"] or "Sin proveedor"
        cam = _camion_label(it)
        ch = it["empleado_chofer_nombre"] or "Sin asignar"
        a = agg.setdefault(prov, {}).setdefault(cam, {}).setdefault(ch, {"venta": 0.0, "rechazo": 0.0, "cambio": 0.0})
        monto = abs(sf(it["importe_total_c_imp"]))
        if es_rechazo_puro(it):
            a["rechazo"] += monto
        elif es_cambio(it):
            a["cambio"] += monto
        elif not es_devolucion(it):
            a["venta"] += monto
    out = {}
    for prov, cams in agg.items():
        out[prov] = {}
        for cam, chs in cams.items():
            out[prov][cam] = {c: {"venta": round(v["venta"], 2), "rechazo": round(v["rechazo"], 2),
                                   "cambio": round(v["cambio"], 2)}
                               for c, v in chs.items()}
    return out


def build_rentabilidad_by_por_camion(items, key_fn):
    """Igual que build_rentabilidad_by pero desglosado por camion, para el filtro global Excluir Camion."""
    agg = {}
    for it in items:
        if es_devolucion(it):
            continue
        cam = _camion_label(it)
        key = key_fn(it) or "Sin asignar"
        a = agg.setdefault(cam, {}).setdefault(key, {"venta": 0.0, "costo": 0.0})
        a["venta"] += abs(sf(it["importe_total_c_imp"]) - sf(it["importe_iva"]))
        a["costo"] += sf(it["precio_costo_unitario"]) * sf(it["cantidad"])
    out = {}
    for cam, keys in agg.items():
        out[cam] = {k: {"venta": round(v["venta"], 2), "costo": round(v["costo"], 2)} for k, v in keys.items()}
    return out


def build_rentabilidad_total_por_camion(items):
    """Rentabilidad total (todos los proveedores juntos) por camion, para Evolucion Mensual."""
    agg = {}
    for it in items:
        if es_devolucion(it):
            continue
        cam = _camion_label(it)
        a = agg.setdefault(cam, {"venta": 0.0, "costo": 0.0})
        a["venta"] += abs(sf(it["importe_total_c_imp"]) - sf(it["importe_iva"]))
        a["costo"] += sf(it["precio_costo_unitario"]) * sf(it["cantidad"])
    return {cam: {"venta": round(v["venta"], 2), "costo": round(v["costo"], 2)} for cam, v in agg.items()}


def build_descuento_by_por_camion(items, key_fn):
    """Igual que build_descuento_by pero desglosado por camion, para el filtro global Excluir Camion."""
    agg = {}
    for it in items:
        if es_devolucion(it):
            continue
        cam = _camion_label(it)
        key = key_fn(it) or "Sin asignar"
        a = agg.setdefault(cam, {}).setdefault(key, {"venta_sin_desc": 0.0, "descuento": 0.0})
        cant = sf(it["cantidad"])
        a["venta_sin_desc"] += sf(it["precio_unitario_s_desc"]) * cant
        a["descuento"] += (sf(it["precio_unitario_s_desc"]) - sf(it["precio_unitario"])) * cant
    out = {}
    for cam, keys in agg.items():
        out[cam] = {k: {"venta_sin_desc": round(v["venta_sin_desc"], 2), "descuento": round(v["descuento"], 2)}
                    for k, v in keys.items()}
    return out


def build_geografia_por_camion(ordenes):
    """Igual que build_geografia pero desglosado por camion (clientes como lista de ids, es
    conteo DISTINCT igual que en build_kpis_por_camion)."""
    agg = {}
    for o in ordenes:
        cam = _camion_label(o)
        loc = (o["localidad"] or "Sin especificar").strip().upper()
        a = agg.setdefault(cam, {}).setdefault(loc, {"venta": 0.0, "rechazo": 0.0, "cambio": 0.0, "clientes": set()})
        monto = sf(o["importe_total"])
        if es_rechazo_puro(o):
            a["rechazo"] += monto
        elif es_cambio(o):
            a["cambio"] += monto
        elif not es_devolucion(o):
            a["venta"] += monto
        if o["cliente_id"] is not None:
            a["clientes"].add(o["cliente_id"])
    out = {}
    for cam, locs in agg.items():
        out[cam] = {}
        for loc, v in locs.items():
            out[cam][loc] = {"venta": round(v["venta"], 2), "rechazo": round(v["rechazo"], 2),
                              "cambio": round(v["cambio"], 2), "clientes": list(v["clientes"])}
    return out


def build_vendedor_por_camion(ordenes):
    """Igual que build_vendedor (solo venta/rechazo/cambio, el objetivo no depende del camion)
    pero desglosado por camion, para el filtro global Excluir Camion."""
    agg = {}
    for o in ordenes:
        cod = str(o["vendedor_codigo"]) if o["vendedor_codigo"] else None
        if not cod:
            continue
        cam = _camion_label(o)
        a = agg.setdefault(cam, {}).setdefault(cod, {"venta": 0.0, "rechazo": 0.0, "cambio": 0.0})
        monto = sf(o["importe_total"])
        if es_rechazo_puro(o):
            a["rechazo"] += monto
        elif es_cambio(o):
            a["cambio"] += monto
        elif not es_devolucion(o):
            a["venta"] += monto
    out = {}
    for cam, cods in agg.items():
        out[cam] = {c: {"venta": round(v["venta"], 2), "rechazo": round(v["rechazo"], 2), "cambio": round(v["cambio"], 2)}
                    for c, v in cods.items()}
    return out


def build_producto_por_camion(items, key_field):
    """Igual que build_producto pero desglosado por camion, sin el tope de top 60 (se aplica
    despues de recalcular en el frontend)."""
    agg = {}
    for it in items:
        if es_devolucion(it):
            continue
        cam = _camion_label(it)
        key = it[key_field] or "Sin especificar"
        a = agg.setdefault(cam, {}).setdefault(key, {"venta": 0.0, "unidades": 0})
        a["venta"] += abs(sf(it["importe_total_c_imp"]))
        a["unidades"] += si(sf(it["cantidad"]))
    out = {}
    for cam, keys in agg.items():
        out[cam] = {k: {"venta": round(v["venta"], 2), "unidades": v["unidades"]} for k, v in keys.items()}
    return out


def build_clientes_por_camion(ordenes):
    """Venta por cliente desglosada por camion, para recalcular la tendencia de Clientes
    (mes actual vs mes anterior) al excluir un camion."""
    agg = {}
    for o in ordenes:
        if o["cliente_id"] is None or es_devolucion(o):
            continue
        cam = _camion_label(o)
        cid = o["cliente_id"]
        a = agg.setdefault(cam, {}).setdefault(cid, {"venta": 0.0, "razon_social": o["razon_social"]})
        a["venta"] += sf(o["importe_total"])
    out = {}
    for cam, clis in agg.items():
        out[cam] = {str(cid): {"venta": round(v["venta"], 2), "razon_social": v["razon_social"]}
                    for cid, v in clis.items()}
    return out


def build_motivo_por_camion(ordenes):
    """Igual que build_motivo pero desglosado por camion, para el filtro global Excluir Camion."""
    agg = {}
    for o in ordenes:
        if not es_rechazo_puro(o):
            continue
        cam = _camion_label(o)
        motivo = o["motivo_rechazo_desc"] or "Sin especificar"
        a = agg.setdefault(cam, {}).setdefault(motivo, {"cantidad": 0, "importe": 0.0})
        a["cantidad"] += 1
        a["importe"] += sf(o["importe_total"])
    out = {}
    for cam, motivos in agg.items():
        out[cam] = {m: {"cantidad": v["cantidad"], "importe": round(v["importe"], 2)} for m, v in motivos.items()}
    return out


def build_motivo_por_prov_por_camion(items):
    """Igual que build_motivo_por_prov pero con un nivel extra de camion."""
    agg = {}
    for it in items:
        if not es_rechazo_puro(it):
            continue
        prov = it["prov_razonsocial"] or "Sin proveedor"
        cam = _camion_label(it)
        motivo = it["motivo_rechazo_desc"] or "Sin especificar"
        a = agg.setdefault(prov, {}).setdefault(cam, {}).setdefault(motivo, {"cantidad": 0, "importe": 0.0})
        a["cantidad"] += 1
        a["importe"] += abs(sf(it["importe_total_c_imp"]))
    out = {}
    for prov, cams in agg.items():
        out[prov] = {}
        for cam, motivos in cams.items():
            out[prov][cam] = {m: {"cantidad": v["cantidad"], "importe": round(v["importe"], 2)} for m, v in motivos.items()}
    return out


def build_interanual_por_prov_por_camion(rows):
    """Contribucion por camion a unidades/peso/venta por proveedor, para un periodo ya fetcheado
    con fetch_venta_periodo (se llama una vez por periodo: actual y anterior, para año y mes)."""
    agg = {}
    for r in rows:
        cam = _camion_label(r)
        prov = r["prov_razonsocial"] or "Sin proveedor"
        a = agg.setdefault(cam, {}).setdefault(prov, {"unidades": 0.0, "peso_kg": 0.0, "venta": 0.0})
        cant = sf(r["cantidad"])
        a["unidades"] += cant
        a["peso_kg"] += cant * sf(r["peso"]) / 1000.0
        a["venta"] += abs(sf(r["importe_total_c_imp"]))
    out = {}
    for cam, provs in agg.items():
        out[cam] = {p: {"unidades": round(v["unidades"]), "peso_kg": round(v["peso_kg"], 1), "venta": round(v["venta"], 2)}
                    for p, v in provs.items()}
    return out


def build_no_compradores_por_camion(rows):
    """Ultima compra por cliente-proveedor, desglosada por camion (la fecha maxima que aporta
    cada camion), para que el frontend pueda recalcular 'ultima compra excluyendo este camion'
    tomando el maximo entre los camiones restantes."""
    agg = {}
    for r in rows:
        ultima = r["ultima_compra"]
        if ultima is None:
            continue
        cam = _camion_label(r)
        cliente_id = r["cliente_id"]
        prov = r["prov_razonsocial"] or "Sin proveedor"
        razon_social = r["razon_social"] or f"Cliente {cliente_id}"
        key = f"{cliente_id}|{prov}"
        d = agg.setdefault(cam, {})
        d[key] = {"cliente_id": cliente_id, "razon_social": razon_social, "proveedor": prov,
                  "ultima_compra": ultima.strftime("%Y-%m-%d")}
    return agg


def build_rentabilidad_by(items, key_fn):
    """Rentabilidad = venta neta (sin IVA) - costo (precio_costo_unitario * cantidad).
    precio_costo_unitario no incluye IVA, por eso la venta se netea de importe_iva antes de comparar
    (importe_total_c_imp SI incluye IVA, como indica su nombre)."""
    agg = {}
    for it in items:
        if es_devolucion(it):
            continue
        key = key_fn(it) or "Sin asignar"
        a = agg.setdefault(key, {"grupo": key, "venta": 0.0, "costo": 0.0})
        a["venta"] += abs(sf(it["importe_total_c_imp"]) - sf(it["importe_iva"]))
        a["costo"] += sf(it["precio_costo_unitario"]) * sf(it["cantidad"])
    out = list(agg.values())
    for a in out:
        a["rentabilidad"] = round(a["venta"] - a["costo"], 2)
        a["pct_rentabilidad"] = round((a["rentabilidad"] / a["venta"] * 100) if a["venta"] else 0, 2)
        a["venta"] = round(a["venta"], 2)
        a["costo"] = round(a["costo"], 2)
    out.sort(key=lambda a: -a["rentabilidad"])
    return out


def build_descuento_by(items, key_fn):
    """Descuento = (precio_unitario_s_desc - precio_unitario) * cantidad.
    El campo venta_item.descuento_importe casi siempre esta en 0 y no refleja el descuento real
    (verificado contra el Power BI corporativo: precio_unitario_s_desc es el precio de lista)."""
    agg = {}
    for it in items:
        if es_devolucion(it):
            continue
        key = key_fn(it) or "Sin asignar"
        a = agg.setdefault(key, {"grupo": key, "venta_sin_desc": 0.0, "descuento": 0.0})
        cant = sf(it["cantidad"])
        a["venta_sin_desc"] += sf(it["precio_unitario_s_desc"]) * cant
        a["descuento"] += (sf(it["precio_unitario_s_desc"]) - sf(it["precio_unitario"])) * cant
    out = list(agg.values())
    for a in out:
        a["pct_descuento"] = round((a["descuento"] / a["venta_sin_desc"] * 100) if a["venta_sin_desc"] else 0, 2)
        a["venta_sin_desc"] = round(a["venta_sin_desc"], 2)
        a["descuento"] = round(a["descuento"], 2)
    out.sort(key=lambda a: -a["descuento"])
    return out


def build_geografia(ordenes):
    agg = {}
    for o in ordenes:
        # normalizamos may/min: la misma localidad aparece con distinta capitalizacion segun la carga
        loc = (o["localidad"] or "Sin especificar").strip().upper()
        a = agg.setdefault(loc, {"localidad": loc, "venta": 0.0, "rechazo": 0.0, "cambio": 0.0, "clientes": set()})
        monto = sf(o["importe_total"])
        if es_rechazo_puro(o):
            a["rechazo"] += monto
        elif es_cambio(o):
            a["cambio"] += monto
        elif not es_devolucion(o):
            a["venta"] += monto
        if o["cliente_id"] is not None:
            a["clientes"].add(o["cliente_id"])
    out = list(agg.values())
    for a in out:
        bruta = a["venta"] + a["rechazo"] + a["cambio"]
        a["pct_rechazo"] = round((a["rechazo"] / bruta * 100) if bruta else 0, 2)
        a["clientes"] = len(a["clientes"])
        a["venta"] = round(a["venta"], 2)
        a["rechazo"] = round(a["rechazo"], 2)
        a["cambio"] = round(a["cambio"], 2)
    out.sort(key=lambda a: -a["venta"])
    return out


def build_vendedor(ordenes, objetivos_mes):
    """Venta real vs objetivo del mes, por vendedor. objetivos_mes: {vendedor_codigo: $objetivo}."""
    agg = {}
    for o in ordenes:
        cod = str(o["vendedor_codigo"]) if o["vendedor_codigo"] else None
        if not cod:
            continue
        nombre = o["vendedor_nombre"] or ("Vendedor " + cod)
        a = agg.setdefault(cod, {"vendedor": nombre, "venta": 0.0, "rechazo": 0.0, "cambio": 0.0})
        monto = sf(o["importe_total"])
        if es_rechazo_puro(o):
            a["rechazo"] += monto
        elif es_cambio(o):
            a["cambio"] += monto
        elif not es_devolucion(o):
            a["venta"] += monto
    for cod, obj in objetivos_mes.items():
        if cod not in agg:
            nombre = None
            agg[cod] = {"vendedor": "Vendedor " + cod, "venta": 0.0, "rechazo": 0.0, "cambio": 0.0}
    out = []
    for cod, a in agg.items():
        objetivo = sf(objetivos_mes.get(cod))
        a["cod"] = cod
        a["objetivo"] = round(objetivo, 2)
        a["pct_cumplimiento"] = round((a["venta"] / objetivo * 100) if objetivo else 0, 2)
        a["venta"] = round(a["venta"], 2)
        a["rechazo"] = round(a["rechazo"], 2)
        a["cambio"] = round(a["cambio"], 2)
        out.append(a)
    out.sort(key=lambda a: -a["venta"])
    return out


def build_producto(items, key_field, label):
    agg = {}
    for it in items:
        if es_devolucion(it):
            continue
        key = it[key_field] or "Sin especificar"
        a = agg.setdefault(key, {label: key, "venta": 0.0, "unidades": 0})
        a["venta"] += abs(sf(it["importe_total_c_imp"]))
        a["unidades"] += si(sf(it["cantidad"]))
    out = list(agg.values())
    for a in out:
        a["venta"] = round(a["venta"], 2)
    out.sort(key=lambda a: -a["venta"])
    return out[:60]


def build_clientes_tendencia(ordenes_actual, ordenes_anterior):
    """Venta por cliente mes actual vs mes anterior. Negativo = cayo, positivo = crecio."""
    def por_cliente(ordenes):
        agg = {}
        for o in ordenes:
            if o["cliente_id"] is None or es_devolucion(o):
                continue
            cid = o["cliente_id"]
            a = agg.setdefault(cid, {"cliente_id": cid, "razon_social": o["razon_social"], "venta": 0.0})
            a["venta"] += sf(o["importe_total"])
        return agg

    actual = por_cliente(ordenes_actual)
    anterior = por_cliente(ordenes_anterior)
    out = []
    for cid, a in actual.items():
        venta_ant = anterior.get(cid, {}).get("venta", 0.0)
        var = a["venta"] - venta_ant
        out.append({
            "cliente_id": cid,
            "razon_social": a["razon_social"],
            "venta": round(a["venta"], 2),
            "venta_mes_anterior": round(venta_ant, 2),
            "variacion": round(var, 2),
            "pct_variacion": round((var / venta_ant * 100) if venta_ant else 0, 2),
        })
    out.sort(key=lambda a: a["variacion"])
    return out[:60]


def build_motivo(ordenes):
    agg = {}
    for o in ordenes:
        if not es_rechazo_puro(o):
            continue
        motivo = o["motivo_rechazo_desc"] or "Sin especificar"
        a = agg.setdefault(motivo, {"motivo": motivo, "cantidad": 0, "importe": 0.0})
        a["cantidad"] += 1
        a["importe"] += sf(o["importe_total"])
    total = sum(a["importe"] for a in agg.values()) or 1
    out = list(agg.values())
    for a in out:
        a["pct"] = round(a["importe"] / total * 100, 2)
        a["importe"] = round(a["importe"], 2)
    out.sort(key=lambda a: -a["importe"])
    return out


def build_motivo_por_prov(items):
    """Motivo de rechazo desglosado por proveedor, para el filtro de la pestana Rechazos."""
    by_prov = {}
    for it in items:
        if not es_rechazo_puro(it):
            continue
        prov = it["prov_razonsocial"] or "Sin proveedor"
        motivo = it["motivo_rechazo_desc"] or "Sin especificar"
        agg = by_prov.setdefault(prov, {})
        a = agg.setdefault(motivo, {"motivo": motivo, "cantidad": 0, "importe": 0.0})
        a["cantidad"] += 1
        a["importe"] += abs(sf(it["importe_total_c_imp"]))
    out = {}
    for prov, agg in by_prov.items():
        total = sum(a["importe"] for a in agg.values()) or 1
        rows = list(agg.values())
        for a in rows:
            a["pct"] = round(a["importe"] / total * 100, 2)
            a["importe"] = round(a["importe"], 2)
        rows.sort(key=lambda a: -a["importe"])
        out[prov] = rows
    return out


def build_chofer_por_prov(items):
    """Venta/rechazo/cambio por chofer desglosado por proveedor.
    Se usa para el filtro de proveedor tanto en Ventas como en Rechazos."""
    by_prov = {}
    for it in items:
        prov = it["prov_razonsocial"] or "Sin proveedor"
        ch = it["empleado_chofer_nombre"] or "Sin asignar"
        agg = by_prov.setdefault(prov, {})
        a = agg.setdefault(ch, {"chofer": ch, "venta": 0.0, "rechazo": 0.0, "cambio": 0.0})
        monto = abs(sf(it["importe_total_c_imp"]))
        if es_rechazo_puro(it):
            a["rechazo"] += monto
        elif es_cambio(it):
            a["cambio"] += monto
        elif not es_devolucion(it):
            a["venta"] += monto
    out = {}
    for prov, agg in by_prov.items():
        rows = list(agg.values())
        for a in rows:
            bruta = a["venta"] + a["rechazo"] + a["cambio"]
            a["pct_rechazo"] = round((a["rechazo"] / bruta * 100) if bruta else 0, 2)
            a["pct_cambio"] = round((a["cambio"] / bruta * 100) if bruta else 0, 2)
            # aproximacion $-ponderada de efectividad (no hay conteo de comprobantes a nivel de linea)
            a["efectividad"] = round((a["venta"] / bruta * 100) if bruta else 0, 2)
            a["venta"] = round(a["venta"], 2)
            a["rechazo"] = round(a["rechazo"], 2)
            a["cambio"] = round(a["cambio"], 2)
        rows.sort(key=lambda a: -a["venta"])
        out[prov] = rows
    return out


def build_routes_and_clientes(ordenes, items):
    prov_por_reparto = {}
    for it in items:
        rid = it["reparto_id"]
        if rid is None:
            continue
        prov = it["prov_razonsocial"] or "Sin proveedor"
        d = prov_por_reparto.setdefault(rid, {})
        d[prov] = d.get(prov, 0.0) + abs(sf(it["importe_total_c_imp"]))

    reparto_agg = {}
    clientes = {}
    for o in ordenes:
        rid = o["reparto_id"]
        if rid is None:
            continue
        r = reparto_agg.setdefault(rid, {
            "reparto_id": rid,
            "reparto_codigo": o["reparto_codigo"],
            "fecha": o["fecha_entrega"].strftime("%Y-%m-%d") if o["fecha_entrega"] else None,
            "chofer": o["empleado_chofer_nombre"] or "Sin asignar",
            "vehiculo": o["vehiculo_descripcion"] or o["vehiculo_codigo"] or "",
            "total": 0.0, "rechazado": 0.0, "clientes": 0,
        })
        r["total"] += sf(o["importe_total"])
        if es_rechazo_puro(o):
            r["rechazado"] += sf(o["importe_total"])
        r["clientes"] += 1

        flag = 3 if es_cambio(o) else (1 if es_rechazo_puro(o) else 0)
        clientes.setdefault(str(rid), []).append([
            o["cliente_id"], o["razon_social"], o["direccion"], o["localidad"],
            o["numero_comprobante"], round(sf(o["importe_total"]), 2), flag,
        ])

    routes = list(reparto_agg.values())
    for r in routes:
        top = sorted(prov_por_reparto.get(r["reparto_id"], {}).items(), key=lambda kv: -kv[1])[:3]
        r["top_prov"] = [{"proveedor": p, "importe": round(v, 2)} for p, v in top]
        bruta = r["total"]
        r["pct_rechazo"] = round((r["rechazado"] / bruta * 100) if bruta else 0, 2)
        r["total"] = round(r["total"], 2)
        r["rechazado"] = round(r["rechazado"], 2)
    routes.sort(key=lambda r: (r["fecha"] or "", r["chofer"]))
    return routes, clientes


def inject_data(html, data_js):
    start_marker = "<script><!-- DATA_START -->"
    end_marker = "<!-- DATA_END --></script>"
    start = html.find(start_marker)
    end = html.find(end_marker)
    if start == -1 or end == -1:
        raise RuntimeError("No se encontraron los marcadores DATA_START/DATA_END en index.html")
    start += len(start_marker)
    return html[:start] + "\n" + data_js + "\n" + html[end:]


def build_mes(ordenes, items, objetivos_mes=None, ordenes_mes_anterior=None):
    kpis = build_kpis(ordenes)
    d_prov = build_prov(items)
    d_chofer = build_chofer(ordenes)
    d_camion = build_camion(ordenes)
    d_kpis_camion = build_kpis_por_camion(ordenes)
    d_prov_camion = build_prov_por_camion(items)
    d_chofer_camion = build_chofer_por_camion(ordenes)
    d_chofer_prov_camion = build_chofer_por_prov_por_camion(items)
    d_motivo = build_motivo(ordenes)
    d_motivo_prov = build_motivo_por_prov(items)
    d_motivo_camion = build_motivo_por_camion(ordenes)
    d_motivo_prov_camion = build_motivo_por_prov_por_camion(items)
    d_chofer_prov = build_chofer_por_prov(items)
    d_routes, d_cli = build_routes_and_clientes(ordenes, items)
    d_rent_prov = build_rentabilidad_by(items, lambda it: it["prov_razonsocial"])
    d_rent_chofer = build_rentabilidad_by(items, lambda it: it["empleado_chofer_nombre"])
    d_rent_prov_camion = build_rentabilidad_by_por_camion(items, lambda it: it["prov_razonsocial"])
    d_rent_chofer_camion = build_rentabilidad_by_por_camion(items, lambda it: it["empleado_chofer_nombre"])
    d_rent_total_camion = build_rentabilidad_total_por_camion(items)
    d_desc_prov = build_descuento_by(items, lambda it: it["prov_razonsocial"])
    d_desc_chofer = build_descuento_by(items, lambda it: it["empleado_chofer_nombre"])
    d_desc_prov_camion = build_descuento_by_por_camion(items, lambda it: it["prov_razonsocial"])
    d_desc_chofer_camion = build_descuento_by_por_camion(items, lambda it: it["empleado_chofer_nombre"])
    d_geo = build_geografia(ordenes)
    d_geo_camion = build_geografia_por_camion(ordenes)
    d_vendedor = build_vendedor(ordenes, objetivos_mes or {})
    d_vendedor_camion = build_vendedor_por_camion(ordenes)
    d_producto = build_producto(items, "item_descripcion", "producto")
    d_rubro = build_producto(items, "rubro_desc", "rubro")
    d_producto_camion = build_producto_por_camion(items, "item_descripcion")
    d_rubro_camion = build_producto_por_camion(items, "rubro_desc")
    d_clientes = build_clientes_tendencia(ordenes, ordenes_mes_anterior or [])
    d_clientes_camion = build_clientes_por_camion(ordenes)
    d_clientes_camion_anterior = build_clientes_por_camion(ordenes_mes_anterior or [])
    return {
        "kpis": kpis,
        "prov": d_prov,
        "chofer": d_chofer,
        "camion": d_camion,
        "kpis_camion": d_kpis_camion,
        "prov_camion": d_prov_camion,
        "chofer_camion": d_chofer_camion,
        "chofer_prov_camion": d_chofer_prov_camion,
        "motivo": d_motivo,
        "motivo_prov": d_motivo_prov,
        "motivo_camion": d_motivo_camion,
        "motivo_prov_camion": d_motivo_prov_camion,
        "chofer_prov": d_chofer_prov,
        "routes": d_routes,
        "cli": d_cli,
        "rent_prov": d_rent_prov,
        "rent_chofer": d_rent_chofer,
        "rent_prov_camion": d_rent_prov_camion,
        "rent_chofer_camion": d_rent_chofer_camion,
        "rent_total_camion": d_rent_total_camion,
        "desc_prov": d_desc_prov,
        "desc_chofer": d_desc_chofer,
        "desc_prov_camion": d_desc_prov_camion,
        "desc_chofer_camion": d_desc_chofer_camion,
        "geo": d_geo,
        "geo_camion": d_geo_camion,
        "vendedor": d_vendedor,
        "vendedor_camion": d_vendedor_camion,
        "producto": d_producto,
        "rubro": d_rubro,
        "producto_camion": d_producto_camion,
        "rubro_camion": d_rubro_camion,
        "clientes": d_clientes,
        "clientes_camion": d_clientes_camion,
        "clientes_camion_anterior": d_clientes_camion_anterior,
        "provs": [p["proveedor"] for p in d_prov],
        "chs": [c["chofer"] for c in d_chofer],
        "camiones": [c["camion"] for c in d_camion],
    }


def main():
    desde, hasta, ahora = rango_historial()
    print(f"Rango: {desde.date()} a {hasta.date()} ({MESES_HISTORIAL} meses)")

    conn = connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        ordenes = fetch_ordenes(cur, desde, hasta)
        items = fetch_items(cur, desde, hasta)
        objetivos_raw = fetch_objetivos(cur)

        desde_i, hasta_i, desde_i_ant, hasta_i_ant = rango_interanual(ahora)
        rows_i_actual = fetch_venta_periodo(cur, desde_i, hasta_i)
        rows_i_anterior = fetch_venta_periodo(cur, desde_i_ant, hasta_i_ant)

        desde_m, hasta_m, desde_m_ant, hasta_m_ant = rango_mes_actual_interanual(ahora)
        rows_m_actual = fetch_venta_periodo(cur, desde_m, hasta_m)
        rows_m_anterior = fetch_venta_periodo(cur, desde_m_ant, hasta_m_ant)

        rows_ultima_compra = fetch_ultima_compra(cur)
    finally:
        conn.close()

    d_no_compradores = build_no_compradores(rows_ultima_compra, ahora)
    d_no_compradores_camion = build_no_compradores_por_camion(rows_ultima_compra)
    print(f"No Compradores: {len(d_no_compradores)} combinaciones cliente-proveedor (de {len(rows_ultima_compra)} totales)")

    d_interanual, d_interanual_total = build_interanual_por_prov(rows_i_actual, rows_i_anterior)
    d_interanual_camion_actual = build_interanual_por_prov_por_camion(rows_i_actual)
    d_interanual_camion_anterior = build_interanual_por_prov_por_camion(rows_i_anterior)
    d_interanual_periodo = {
        "actual": f"{desde_i.strftime('%d/%m/%Y')} – {ahora.strftime('%d/%m/%Y')}",
        "anterior": f"{desde_i_ant.strftime('%d/%m/%Y')} – {(hasta_i_ant - timedelta(days=1)).strftime('%d/%m/%Y')}",
    }
    print(f"Interanual (año): {len(rows_i_actual)} lineas periodo actual, {len(rows_i_anterior)} lineas periodo anterior")

    d_interanual_mes, d_interanual_mes_total = build_interanual_por_prov(rows_m_actual, rows_m_anterior)
    d_interanual_mes_camion_actual = build_interanual_por_prov_por_camion(rows_m_actual)
    d_interanual_mes_camion_anterior = build_interanual_por_prov_por_camion(rows_m_anterior)
    d_interanual_mes_periodo = {
        "actual": f"{desde_m.strftime('%d/%m/%Y')} – {ahora.strftime('%d/%m/%Y')}",
        "anterior": f"{desde_m_ant.strftime('%d/%m/%Y')} – {(hasta_m_ant - timedelta(days=1)).strftime('%d/%m/%Y')}",
    }
    print(f"Interanual (mes): {len(rows_m_actual)} lineas periodo actual, {len(rows_m_anterior)} lineas periodo anterior")

    print(f"Ordenes: {len(ordenes)} | Lineas: {len(items)} | Filas objetivo: {len(objetivos_raw)}")

    # "OBJ JULIO 2026" -> "2026-07"
    mes_nombre_a_num = {v.upper(): k for k, v in MES_NOMBRE.items()}
    objetivo_por_mes = {}
    for row in objetivos_raw:
        desc = (row["descripcion"] or "").upper().replace("OBJ", "").strip()
        partes = desc.split()
        if len(partes) != 2 or partes[0] not in mes_nombre_a_num:
            continue
        m = f"{partes[1]}-{mes_nombre_a_num[partes[0]]:02d}"
        objetivo_por_mes.setdefault(m, {})[str(row["vendedor_codigo"])] = float(row["objetivo"] or 0)

    ordenes_por_mes = {}
    for o in ordenes:
        ordenes_por_mes.setdefault(mes_key(o["fecha_entrega"]), []).append(o)
    items_por_mes = {}
    for it in items:
        items_por_mes.setdefault(mes_key(it["fecha_entrega"]), []).append(it)

    meses = sorted(set(ordenes_por_mes) | set(items_por_mes), reverse=True)
    d_data = {}
    d_mes_label = {}
    for m in meses:
        anio, mes_num = m.split("-")
        d_mes_label[m] = f"{MES_NOMBRE[int(mes_num)]} {anio}"
        d_data[m] = build_mes(
            ordenes_por_mes.get(m, []), items_por_mes.get(m, []),
            objetivos_mes=objetivo_por_mes.get(m, {}),
            ordenes_mes_anterior=ordenes_por_mes.get(mes_anterior(m), []),
        )
        print(f"  {m}: {len(ordenes_por_mes.get(m, []))} ordenes, {len(items_por_mes.get(m, []))} lineas")

    mes_actual = meses[0] if meses else mes_key(ahora)

    d_evolucion = [
        {
            "mes": m,
            "mes_label": d_mes_label[m],
            "venta": d_data[m]["kpis"].get("venta_neta", 0),
            "rechazo": d_data[m]["kpis"].get("rechazo_monto", 0),
            "pct_rechazo": d_data[m]["kpis"].get("pct_rechazo", 0),
            "rentabilidad": round(sum(p["rentabilidad"] for p in d_data[m]["rent_prov"]), 2),
            "pct_rentabilidad": round(
                (sum(p["rentabilidad"] for p in d_data[m]["rent_prov"]) / sum(p["venta"] for p in d_data[m]["rent_prov"]) * 100)
                if sum(p["venta"] for p in d_data[m]["rent_prov"]) else 0, 2,
            ),
        }
        for m in sorted(meses)
    ]

    # contribucion por camion a cada mes de Evolucion Mensual (kpis ya calculado en build_mes,
    # rentabilidad total se recalcula ahi mismo), para el filtro global Excluir Camion.
    d_evolucion_camion = {
        m: {"kpis": d_data[m]["kpis_camion"], "rent": d_data[m]["rent_total_camion"]}
        for m in meses
    }

    # ---- datos por vendedor (login individual) ----
    vnom = {}
    for o in ordenes:
        cod = o["vendedor_codigo"]
        if cod:
            vnom[str(cod)] = o["vendedor_nombre"] or ("Vendedor " + str(cod))
    vvalidos = sorted(vnom.keys(), key=lambda c: (len(c), c))
    print(f"Vendedores activos: {vvalidos}")

    d_vend_data = {}
    for cod in vvalidos:
        ord_v = [o for o in ordenes if str(o["vendedor_codigo"]) == cod]
        it_v = [it for it in items if str(it["vendedor_codigo"]) == cod]
        ord_v_por_mes = {}
        for o in ord_v:
            ord_v_por_mes.setdefault(mes_key(o["fecha_entrega"]), []).append(o)
        it_v_por_mes = {}
        for it in it_v:
            it_v_por_mes.setdefault(mes_key(it["fecha_entrega"]), []).append(it)
        meses_v = sorted(set(ord_v_por_mes) | set(it_v_por_mes), reverse=True)
        d_vend_data[cod] = {
            m: build_mes(
                ord_v_por_mes.get(m, []), it_v_por_mes.get(m, []),
                objetivos_mes={cod: objetivo_por_mes.get(m, {}).get(cod)} if objetivo_por_mes.get(m, {}).get(cod) is not None else {},
                ordenes_mes_anterior=ord_v_por_mes.get(mes_anterior(m), []),
            )
            for m in meses_v
        }

    blocks = [
        make_json("D_MESES", meses),
        make_json("D_MES_LABEL", d_mes_label),
        make_json("D_MES_ACTUAL", mes_actual),
        make_json("D_DATA", d_data),
        make_json("D_EVOLUCION", d_evolucion),
        make_json("D_EVOLUCION_CAMION", d_evolucion_camion),
        make_json("D_INTERANUAL", d_interanual),
        make_json("D_INTERANUAL_TOTAL", d_interanual_total),
        make_json("D_INTERANUAL_PERIODO", d_interanual_periodo),
        make_json("D_INTERANUAL_CAMION_ACTUAL", d_interanual_camion_actual),
        make_json("D_INTERANUAL_CAMION_ANTERIOR", d_interanual_camion_anterior),
        make_json("D_INTERANUAL_MES", d_interanual_mes),
        make_json("D_INTERANUAL_MES_TOTAL", d_interanual_mes_total),
        make_json("D_INTERANUAL_MES_PERIODO", d_interanual_mes_periodo),
        make_json("D_INTERANUAL_MES_CAMION_ACTUAL", d_interanual_mes_camion_actual),
        make_json("D_INTERANUAL_MES_CAMION_ANTERIOR", d_interanual_mes_camion_anterior),
        make_json("D_NO_COMPRADORES", d_no_compradores),
        make_json("D_NO_COMPRADORES_CAMION", d_no_compradores_camion),
        make_json("D_VVALIDOS", vvalidos),
        make_json("D_VNOM", vnom),
        make_json("D_VEND_DATA", d_vend_data),
    ]
    data_js = "\n".join(blocks)

    html_path = os.path.join(BASE_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    html = inject_data(html, data_js)
    html = html.replace(
        'id="hdr-build-ts"></span>',
        f'id="hdr-build-ts">{ahora.strftime("%d/%m/%Y %H:%M")}</span>',
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("index.html actualizado correctamente.")


if __name__ == "__main__":
    main()
