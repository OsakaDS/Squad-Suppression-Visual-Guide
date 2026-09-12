"""Minimal UE5.7 (Squad v10.5.3) .uasset reader: name table, imports, exports, tagged properties."""
import struct, os

class Reader:
    def __init__(self, data, off=0):
        self.d = data; self.o = off
    def i32(self):
        v = struct.unpack_from('<i', self.d, self.o)[0]; self.o += 4; return v
    def u32(self):
        v = struct.unpack_from('<I', self.d, self.o)[0]; self.o += 4; return v
    def i64(self):
        v = struct.unpack_from('<q', self.d, self.o)[0]; self.o += 8; return v
    def u8(self):
        v = self.d[self.o]; self.o += 1; return v
    def f32(self):
        v = struct.unpack_from('<f', self.d, self.o)[0]; self.o += 4; return v
    def f64(self):
        v = struct.unpack_from('<d', self.d, self.o)[0]; self.o += 8; return v
    def fstring(self):
        n = self.i32()
        if n == 0: return ''
        if n < 0:
            s = self.d[self.o:self.o-2*n-2].decode('utf-16-le', 'replace'); self.o += -2*n
        else:
            s = self.d[self.o:self.o+n-1].decode('utf-8', 'replace'); self.o += n
        return s

def _entry_ok(data, off):
    if off < 0 or off + 4 > len(data): return None
    ln = struct.unpack_from('<i', data, off)[0]
    if ln <= 0 or ln > 1024: return None
    end = off + 4 + ln
    if end + 4 > len(data): return None
    s = data[off+4:end]
    if s[-1] != 0: return None
    body = s[:-1]
    if any(c < 32 or c > 126 for c in body): return None
    return (body.decode('ascii'), end + 4)

class Package:
    def __init__(self, path):
        self.path = path
        self.d = open(path, 'rb').read()
        self._parse_summary()
        self._parse_names()
        self._parse_imports()
        self._parse_exports()

    def _parse_summary(self):
        d = self.d
        assert d[:4] == b'\xc1\x83\x2a\x9e', 'not a uasset'
        # locate package name FString: first '/Game' or '/Engine' string after custom versions
        p = d.find(b'/Game/', 0x18)
        if p == -1: p = d.find(b'/Engine/', 0x18)
        # walk back to length prefix
        start = None
        for back in range(4, 8):
            cand = p - back
            ln = struct.unpack_from('<i', d, cand)[0] if cand >= 0 else -1
            if ln > 0 and cand + 4 == p:
                start = cand; break
        r = Reader(d, start)
        self.package_name = r.fstring()
        self.package_flags = r.u32()
        self.name_count = r.i32(); self.name_offset = r.i32()
        self.soft_count = r.i32(); self.soft_offset = r.i32()
        self.localization_id = r.fstring()
        self.gatherable_count = r.i32(); self.gatherable_offset = r.i32()
        self.export_count = r.i32(); self.export_offset = r.i32()
        self.import_count = r.i32(); self.import_offset = r.i32()

    def _parse_names(self):
        self.names = []
        off = self.name_offset
        for _ in range(self.name_count):
            r = _entry_ok(self.d, off)
            if not r: break
            self.names.append(r[0]); off = r[1]

    def fname(self, off):
        i, n = struct.unpack_from('<ii', self.d, off)
        s = self.names[i] if 0 <= i < len(self.names) else f'<{i}>'
        return s if n == 0 else f'{s}_{n-1}'

    def _parse_imports(self):
        self.imports = []
        stride = 40
        for k in range(self.import_count):
            o = self.import_offset + k * stride
            self.imports.append({
                'class_package': self.fname(o), 'class_name': self.fname(o+8),
                'outer': struct.unpack_from('<i', self.d, o+16)[0],
                'name': self.fname(o+20), 'package': self.fname(o+28)})

    def _parse_exports(self):
        self.exports = []
        total = (self.gatherable_offset - self.export_offset) if self.gatherable_offset > self.export_offset else 0
        stride = 112
        for k in range(self.export_count):
            o = self.export_offset + k * stride
            ci, si, ti, oi = struct.unpack_from('<4i', self.d, o)
            name = self.fname(o+16)
            flags = struct.unpack_from('<I', self.d, o+24)[0]
            ssize, soff = struct.unpack_from('<qq', self.d, o+28)
            self.exports.append({'name': name, 'class': ci, 'super': si, 'template': ti,
                                 'outer': oi, 'flags': flags, 'size': ssize, 'offset': soff})

    def resolve(self, idx):
        """package index -> readable object name"""
        if idx == 0: return None
        if idx < 0:
            k = -idx - 1
            if k >= len(self.imports): return f'<import {idx}>'
            imp = self.imports[k]
            outer = self.resolve(imp['outer'])
            return f"{outer}.{imp['name']}" if outer and not outer.startswith('/Script') else (
                   f"{outer}.{imp['name']}" if outer else imp['name'])
        k = idx - 1
        if k >= len(self.exports): return f'<export {idx}>'
        return self.exports[k]['name']

    # ---------- tagged properties ----------
    def read_typename(self, r):
        name = self.fname(r.o); r.o += 8
        cnt = r.i32()
        params = [self.read_typename(r) for _ in range(cnt)]
        return {'name': name, 'params': params}

    def read_props(self, off, end, depth=0):
        props = []
        r = Reader(self.d, off)
        while r.o < end - 8:
            name = self.fname(r.o); r.o += 8
            if name == 'None': break
            tn = self.read_typename(r)
            size = r.i32()
            flags = r.u8()
            arr_idx = 0
            if flags & 1: arr_idx = r.i32()
            if flags & 2: r.o += 16
            if flags & 4:
                ext = r.u32()
                if ext & 1: r.o += 16
            vstart = r.o
            val = self.read_value(tn, vstart, vstart + size, depth)
            props.append({'name': name, 'type': tn['name'], 'typename': tn,
                          'index': arr_idx, 'size': size, 'value': val})
            r.o = vstart + size
        return props

    def read_value(self, tn, off, end, depth=0):
        t = tn['name']; r = Reader(self.d, off)
        try:
            if t == 'FloatProperty': return r.f32()
            if t == 'DoubleProperty': return r.f64()
            if t in ('IntProperty', 'Int32Property'): return r.i32()
            if t == 'UInt32Property': return r.u32()
            if t == 'Int64Property': return r.i64()
            if t == 'BoolProperty': return bool(r.u8()) if end > off else None
            if t == 'ByteProperty':
                if end - off == 1: return r.u8()
                return self.fname(off)
            if t == 'EnumProperty': return self.fname(off)
            if t == 'NameProperty': return self.fname(off)
            if t == 'StrProperty': return r.fstring()
            if t == 'TextProperty':
                flags = r.u32(); hist = struct.unpack_from('<b', self.d, r.o)[0]; r.o += 1
                if hist == 0:                      # Base: namespace / key / source
                    ns = r.fstring(); key = r.fstring(); src = r.fstring()
                    return {'text': src, 'key': key}
                if hist == -1:                     # None, optionally culture-invariant
                    if r.o + 4 <= end and r.i32():
                        return {'text': r.fstring(), 'key': None}
                    return {'text': None, 'key': None}
                return {'text': None, 'key': None}
            if t in ('ObjectProperty', 'ClassProperty'):
                return self.resolve(r.i32())
            if t in ('SoftObjectProperty', 'SoftClassProperty'):
                return r.fstring()
            if t == 'ArrayProperty':
                n = r.i32()
                inner = tn['params'][0] if tn['params'] else {'name': '?', 'params': []}
                items = []
                if inner['name'] == 'StructProperty':
                    # array of structs: elements are raw struct data back to back
                    return {'count': n, 'inner': inner['name'], 'raw_range': (r.o, end)}
                esz = {'FloatProperty': 4, 'IntProperty': 4, 'ObjectProperty': 4,
                       'NameProperty': 8, 'DoubleProperty': 8, 'BoolProperty': 1,
                       'ByteProperty': 1}.get(inner['name'])
                if esz:
                    for _ in range(n):
                        items.append(self.read_value(inner, r.o, r.o + esz, depth+1)); r.o += esz
                    return items
                return {'count': n, 'inner': inner['name'], 'raw_range': (r.o, end)}
            if t == 'StructProperty':
                sname = tn['params'][0]['name'] if tn['params'] else '?'
                return self.read_struct(sname, off, end, depth)
        except Exception as e:
            return f'<err {e}>'
        return {'type': t, 'raw': self.d[off:end].hex(' ')[:120]}

    def read_struct(self, sname, off, end, depth=0):
        r = Reader(self.d, off)
        if sname in ('Vector', 'Rotator'):
            return [r.f64(), r.f64(), r.f64()] if end - off >= 24 else [r.f32(), r.f32(), r.f32()]
        if sname == 'Vector2D':
            return [r.f64(), r.f64()] if end - off >= 16 else [r.f32(), r.f32()]
        if sname == 'Guid':
            return self.d[off:off+16].hex()
        if sname in ('FloatRange', 'FloatInterval'):
            return {'raw': self.d[off:end].hex(' ')}
        # generic: nested tagged properties
        sub = self.read_props(off, end, depth+1)
        if sub: return {'struct': sname, 'props': sub}
        return {'struct': sname, 'raw': self.d[off:end].hex(' ')[:200]}

    def export_props(self, exp):
        off, end = exp['offset'], exp['offset'] + exp['size']
        # skip leading bytes until a plausible tag
        for skip in range(0, 8):
            o = off + skip
            i, n = struct.unpack_from('<ii', self.d, o)
            if 0 <= i < len(self.names) and n == 0:
                nm = self.names[i]
                if nm != 'None':
                    j, m = struct.unpack_from('<ii', self.d, o + 8)
                    if 0 <= j < len(self.names) and self.names[j].endswith('Property'):
                        return self.read_props(o, end)
        return []

    def cdo(self):
        for e in self.exports:
            if e['name'].startswith('Default__'): return e
        return None
