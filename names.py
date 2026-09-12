import struct, sys

def find_name_table(data):
    # find candidate start: search for length-prefixed ANSI strings chain
    # locate a known early name
    best = None
    for probe in (b'ArrayProperty\x00', b'BoolProperty\x00', b'None\x00'):
        idx = data.find(probe)
        while idx != -1:
            start = idx - 4
            ln = struct.unpack_from('<i', data, start)[0]
            if ln == len(probe):
                # walk backwards to find table start
                cur = start
                # walk forward first to validate
                return walk_back(data, cur)
            idx = data.find(probe, idx+1)
    return None

def entry_ok(data, off):
    if off < 0 or off+4 > len(data): return None
    ln = struct.unpack_from('<i', data, off)[0]
    if ln <= 0 or ln > 512: return None
    end = off+4+ln
    if end+4 > len(data): return None
    s = data[off+4:end]
    if s[-1] != 0: return None
    body = s[:-1]
    try: txt = body.decode('ascii')
    except: return None
    if any(c < 32 for c in body): return None
    return (txt, end+4)

def walk_back(data, off):
    # step back to previous entries while valid
    cur = off
    while True:
        found = None
        for back in range(6, 600):
            cand = cur - back
            r = entry_ok(data, cand)
            if r and r[1] == cur:
                found = cand
                break
        if found is None: break
        cur = found
    return cur

def parse_names(data):
    start = find_name_table(data)
    names = []
    off = start
    while True:
        r = entry_ok(data, off)
        if not r: break
        names.append(r[0]); off = r[1]
    return start, names, off

if __name__ == '__main__':
    data = open(sys.argv[1],'rb').read()
    start, names, end = parse_names(data)
    print("table start", hex(start), "count", len(names), "end", hex(end))
    for i,n in enumerate(names): print(i, n)
