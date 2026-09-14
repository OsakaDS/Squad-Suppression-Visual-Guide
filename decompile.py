"""Turn parsed Blueprint graphs into readable pseudo-code."""
import re, sys, collections
from graph import Graph

INFIX = {
 'Multiply':'*','Add':'+','Subtract':'-','Divide':'/','Less':'<','LessEqual':'<=','Greater':'>','GreaterEqual':'>=',
 'EqualEqual':'==','NotEqual':'!=','BooleanAND':'and','BooleanOR':'or','Percent':'%','Not_PreBool':'not',
}
def opname(fn):
    base = fn.split('_')[0] if '_' in fn and fn.split('_')[1] and fn.split('_')[1][0].isupper() else fn
    if fn == 'Not_PreBool': return 'not'
    return INFIX.get(base)

class Decompiler:
    def __init__(self, g):
        self.g = g; self.P = g.p
        self.nodes = g.nodes
        self.pinmap = {(n['idx'], p['id']): (n, p) for n in self.nodes.values() for p in n['pins']}
        self.out = []; self.visited = set(); self.callcount = collections.Counter()

    # ---- helpers ----
    def member(self, n, key):
        v = n['props'].get(key)
        if not isinstance(v, dict): return {}
        return {q['name']: q['value'] for q in v.get('props', [])}
    def fn_name(self, n):
        m = self.member(n, 'FunctionReference'); return m.get('MemberName') or '?'
    def var_name(self, n):
        m = self.member(n, 'VariableReference'); return m.get('MemberName') or '?'
    def objname(self, idx):
        # tagged-property object refs arrive already resolved to a path string; raw pin refs are ints
        s = idx if isinstance(idx, str) else (self.P.resolve(idx) or '')
        return (s or 'None').split('.')[-1].replace('_C', '')
    def isexec(self, p): return p['type']['cat'] == 'exec'
    def ins(self, n):  return [p for p in n['pins'] if p['dir']=='in' and not self.isexec(p)]
    def operands(self, n):
        """data inputs that matter: drop the library 'self' pin and unwired pins with no default"""
        return [p for p in self.ins(n) if p['name'] not in ('self','Target','WorldContextObject')
                and (p['linked'] or p['default'] or p['defobj'] or p['type']['cat'] in ('real','int','bool','byte'))]
    def outs(self, n): return [p for p in n['pins'] if p['dir']=='out' and not self.isexec(p)]
    def exec_outs(self, n): return [p for p in n['pins'] if p['dir']=='out' and self.isexec(p)]
    def src(self, p):
        """the (node, pin) feeding this input pin, following reroute knots"""
        if not p['linked']: return None
        n2, p2 = self.pinmap[p['linked'][0]]
        while n2['cls'] == 'K2Node_Knot':
            inp = [q for q in n2['pins'] if q['dir']=='in'][0]
            if not inp['linked']: return None
            n2, p2 = self.pinmap[inp['linked'][0]]
        return n2, p2

    # ---- expressions ----
    def default(self, p):
        t = p['type']
        if p['defobj']: return self.objname(p['defobj'])
        v = p['default']
        if t['cat'] in ('object','class','softobject') and not v: return 'self' if p['name'] in ('self','Target') else 'None'
        if t['cat']=='bool': return v.lower() if v else 'false'
        if t['cat'] in ('real','int','byte') and v: return v
        if t['cat']=='struct' and v: return v
        if t['cat']=='name' and v: return v
        if t['cat']=='string' and v: return repr(v)
        if t['cat']=='text' and p['deftext']: return repr(p['deftext'])
        if v: return v
        return {'real':'0','int':'0','bool':'false','name':'None'}.get(t['cat'], '<none>')
    def expr(self, p, depth=0):
        s = self.src(p)
        if not s: return self.default(p)
        n2, p2 = s
        return self.out_expr(n2, p2, depth+1)
    def args(self, n, skip=('self','Target','WorldContextObject'), depth=0):
        parts = []
        for p in self.ins(n):
            if p['name'] in skip and not p['linked']: continue
            parts.append(f"{p['name']}={self.expr(p, depth)}")
        return ', '.join(parts)
    def out_expr(self, n, p, depth=0):
        if depth > 12: return '…'
        c = n['cls']
        if c == 'K2Node_VariableGet': return self.var_name(n)
        if c == 'K2Node_Self': return 'self'
        if c in ('K2Node_FunctionEntry','K2Node_Event','K2Node_CustomEvent'): return p['name']
        if c in ('K2Node_PromotableOperator','K2Node_CommutativeAssociativeBinaryOperator','K2Node_CallFunction'):
            fn = self.fn_name(n); op = opname(fn)
            ops = self.operands(n)
            if op == 'not': return f"not ({self.expr(ops[0], depth)})"
            if op and len(ops) >= 2:
                return '(' + f' {op} '.join(self.expr(q, depth) for q in ops) + ')'
            outs = self.outs(n)
            tgt = next((q for q in self.ins(n) if q['name'] in ('self','Target')), None)
            recv = (self.expr(tgt, depth) + '.') if (tgt and tgt['linked']) else ''
            pure = not any(self.isexec(q) for q in n['pins'])   # pure calls have no exec pins
            call = f"{recv}{fn}({self.args(n, depth=depth)})" if pure else f"«{fn}»"
            if len(outs) > 1: return f"{call}.{p['name']}"
            return call
        if c == 'K2Node_Select':
            ins = self.ins(n); idx = next((q for q in ins if q['name']=='Index'), None)
            opts = [q for q in ins if q is not idx]
            return f"select({self.expr(idx, depth)}: " + ', '.join(f"{q['name']}→{self.expr(q, depth)}" for q in opts) + ')'
        if c == 'K2Node_MakeStruct':
            return '{' + ', '.join(f"{q['name']}: {self.expr(q, depth)}" for q in self.ins(n) if q['linked'] or q['default']) + '}'
        if c == 'K2Node_BreakStruct':
            return f"{self.expr(self.ins(n)[0], depth)}.{p['name']}"
        if c == 'K2Node_DynamicCast':
            return f"Cast<{self.objname(n['props'].get('TargetType', 0))}>({self.expr(self.ins(n)[0], depth)})"
        if c == 'K2Node_GetSubsystem':
            return f"Subsystem<{self.objname(n['props'].get('CustomClass', 0))}>"
        if c == 'K2Node_MacroInstance':
            return f"{self.macro(n)}.{p['name']}"
        if c == 'K2Node_Timeline':
            return f"Timeline[{n['props'].get('TimelineName')}].{p['name']}"
        if c == 'K2Node_GetArrayItem':
            ins = self.ins(n); return f"{self.expr(ins[0], depth)}[{self.expr(ins[1], depth)}]"
        if c == 'K2Node_CreateDelegate':
            return f"delegate({n['props'].get('SelectedFunctionName')})"
        if c in ('K2Node_Tunnel','K2Node_Composite'): return f"{n['name']}.{p['name']}"
        return f"{c.replace('K2Node_','')}.{p['name']}"
    def macro(self, n):
        m = self.member(n, 'MacroGraphReference')
        mg = m.get('MacroGraph')
        return (self.P.resolve(mg) or 'Macro').split('.')[-1] if isinstance(mg, int) else str(mg or 'Macro').split('.')[-1]

    # ---- statements ----
    def emit(self, ind, s): self.out.append('  '*ind + s)
    def walk(self, n, ind=0, exec_pin_name=None):
        """follow exec flow from node n; prints statements"""
        while n is not None:
            key = n['idx']
            if key in self.visited:
                self.emit(ind, f"→ continues at [{key}] {self.stmt_label(n)}"); return
            self.visited.add(key)
            c = n['cls']
            ex = self.exec_outs(n)
            if c == 'K2Node_IfThenElse':
                cond = next(q for q in self.ins(n) if q['name']=='Condition')
                self.emit(ind, f"if {self.expr(cond)}:")
                t = next((q for q in ex if q['name'] in ('then','Then','True')), None)
                f = next((q for q in ex if q['name'] in ('else','Else','False')), None)
                self.branch(t, ind+1); 
                if f and f['linked']:
                    self.emit(ind, "else:"); self.branch(f, ind+1)
                return
            if c == 'K2Node_ExecutionSequence':
                for i, q in enumerate(ex):
                    if q['linked']:
                        self.emit(ind, f"sequence step {i}:"); self.branch(q, ind+1)
                return
            if c == 'K2Node_DynamicCast' and ex:
                self.emit(ind, f"if {self.out_expr(n, self.outs(n)[0])} succeeds:")
                ok = next((q for q in ex if 'Fail' not in q['name']), None); fail = next((q for q in ex if 'Fail' in q['name']), None)
                self.branch(ok, ind+1)
                if fail and fail['linked']: self.emit(ind, "else:"); self.branch(fail, ind+1)
                return
            if c == 'K2Node_SwitchEnum':
                sel = self.ins(n)[0]
                self.emit(ind, f"switch {self.expr(sel)}:")
                for q in ex:
                    if q['linked']: self.emit(ind+1, f"case {q['name']}:"); self.branch(q, ind+2)
                return
            if c == 'K2Node_MacroInstance' and len(ex) > 1:
                self.emit(ind, f"{self.macro(n)}({self.args(n, skip=())}):")
                for q in ex:
                    if q['linked']: self.emit(ind+1, f"{q['name']}:"); self.branch(q, ind+2)
                return
            if c == 'K2Node_Timeline' and len(ex) > 1:
                self.emit(ind, f"Timeline[{n['props'].get('TimelineName')}]:")
                for q in ex:
                    if q['linked']: self.emit(ind+1, f"on {q['name']}:"); self.branch(q, ind+2)
                return
            if c == 'K2Node_Composite':
                gname = self.bound_graph_name(n)
                self.emit(ind, f"# ── enter collapsed graph '{gname}' ──")
                entry = next((m for m in self.nodes.values() if m['graph'] == gname and m['cls']=='K2Node_Tunnel' and self.exec_outs(m)), None)
                if entry: self.branch(self.exec_outs(entry)[0], ind+1)
                self.emit(ind, f"# ── leave '{gname}' ──")
            # plain statement
            s = self.stmt(n)
            if s: self.emit(ind, s)
            # single successor
            nxt = next((q for q in ex if q['linked']), None)
            if len([q for q in ex if q['linked']]) > 1:
                for q in ex:
                    if q['linked']: self.emit(ind, f"{q['name']}:"); self.branch(q, ind+1)
                return
            if not nxt: return
            n = self.pinmap[nxt['linked'][0]][0]
            while n['cls'] == 'K2Node_Knot':
                o = self.exec_outs(n)
                if not o or not o[0]['linked']: return
                n = self.pinmap[o[0]['linked'][0]][0]
    def branch(self, pin, ind):
        if not pin or not pin['linked']: self.emit(ind, 'pass'); return
        n = self.pinmap[pin['linked'][0]][0]
        while n['cls'] == 'K2Node_Knot':
            o = self.exec_outs(n)
            if not o or not o[0]['linked']: return
            n = self.pinmap[o[0]['linked'][0]][0]
        self.walk(n, ind)
    def stmt_label(self, n):
        c = n['cls']
        if c == 'K2Node_CallFunction': return self.fn_name(n)
        if c == 'K2Node_VariableSet': return 'set ' + self.var_name(n)
        return c.replace('K2Node_','')
    def stmt(self, n):
        c = n['cls']
        if c in ('K2Node_FunctionEntry','K2Node_Event','K2Node_CustomEvent'):
            params = ', '.join(f"{p['name']}: {p['type']['cat']}" for p in self.outs(n))
            return f"ENTRY {self.entry_name(n)}({params})"
        if c == 'K2Node_CallFunction':
            fn = self.fn_name(n); outs = self.outs(n)
            tgt = next((q for q in self.ins(n) if q['name'] in ('self','Target')), None)
            recv = (self.expr(tgt) + '.') if (tgt and tgt['linked']) else ''
            lhs = ''
            used = [o for o in outs if o['linked']]
            if used: lhs = ', '.join(f"{fn}.{o['name']}" if len(outs)>1 else fn for o in used) + ' = '
            return f"{lhs}{recv}{fn}({self.args(n)})"
        if c == 'K2Node_VariableSet':
            val = next((q for q in self.ins(n) if q['name'] not in ('self','Target')), None)
            return f"{self.var_name(n)} = {self.expr(val) if val else '?'}"
        if c == 'K2Node_FunctionResult':
            return 'return ' + ', '.join(f"{q['name']}={self.expr(q)}" for q in self.ins(n))
        if c in ('K2Node_AddDelegate','K2Node_AssignDelegate'):
            d = self.member(n, 'DelegateReference').get('MemberName')
            src = next((q for q in self.ins(n) if q['type']['cat']=='delegate'), None)
            return f"bind {d} += {self.expr(src) if src else '?'}"
        if c == 'K2Node_RemoveDelegate':
            return f"unbind {self.member(n, 'DelegateReference').get('MemberName')}"
        if c == 'K2Node_CallDelegate':
            return f"broadcast {self.member(n, 'DelegateReference').get('MemberName')}({self.args(n)})"
        if c == 'K2Node_MacroInstance':
            return f"{self.macro(n)}({self.args(n, skip=())})"
        if c == 'K2Node_Timeline':
            return f"Timeline[{n['props'].get('TimelineName')}]"
        if c == 'K2Node_Composite': return f"[collapsed graph: {self.bound_graph_name(n)}]"
        if c == 'K2Node_Tunnel': return None
        if c == 'K2Node_InputKey':
            k = self.member(n, 'InputKey').get('KeyName'); return f"ENTRY key {k}"
        return c.replace('K2Node_','') + f"({self.args(n)})"
    def bound_graph_name(self, n):
        bg = n['props'].get('BoundGraph')
        return (bg if isinstance(bg, str) else str(bg)).split('.')[-1]
    def entry_name(self, n):
        pr = n['props']
        return pr.get('CustomFunctionName') or self.member(n,'EventReference').get('MemberName') or self.member(n,'FunctionReference').get('MemberName') or n['name']

    def run(self, entry_filter):
        for n in sorted(self.nodes.values(), key=lambda n: (n['graph'], n['props'].get('NodePosY',0))):
            if n['cls'] in ('K2Node_FunctionEntry','K2Node_Event','K2Node_CustomEvent','K2Node_InputKey'):
                name = self.entry_name(n) if n['cls']!='K2Node_InputKey' else 'key '+str(self.member(n,'InputKey').get('KeyName'))
                if not entry_filter(n['graph'], name): continue
                self.out.append(''); self.out.append(f"##### {n['graph']} :: {name}   [node {n['idx']}]")
                self.walk(n, 0)
        return '\n'.join(self.out)

if __name__ == '__main__':
    g = Graph(sys.argv[1])
    d = Decompiler(g)
    want = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else re.compile('.')
    print(d.run(lambda graph, name: bool(want.search(graph + ' ' + name))))
