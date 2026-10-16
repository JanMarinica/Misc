"""Convert a Universal Robots .urp (gzipped XStream XML) into readable indented pseudocode."""
import gzip, math, re, sys
from lxml import etree

def load(path):
    data = gzip.open(path).read() if path.endswith('.urp') else open(path, 'rb').read()
    return etree.fromstring(data)

def resolve(el):
    """Follow XStream relative 'reference' attributes."""
    seen = 0
    while el is not None and el.get('reference') is not None and seen < 50:
        cur = el
        for part in el.get('reference').split('/'):
            if part == '..':
                cur = cur.getparent()
            elif part:
                m = re.match(r'([\w.\-]+)(?:\[(\d+)\])?$', part)
                tag, idx = m.group(1), int(m.group(2) or 1)
                kids = [c for c in cur if c.tag == tag]
                cur = kids[idx - 1]
                if cur.get('reference') is not None:
                    cur = resolve(cur)
        el = cur
        seen += 1
    return el

def name_of(el):
    el = resolve(el)
    if el is None: return '?'
    return el.get('name') or el.get('referencedName') or el.get('referenceName') or el.get('featureName') or '?'

def expr(e):
    if e is None: return ''
    out = []
    for t in e:
        if t.tag == 'ExpressionChar': out.append(t.get('character'))
        elif t.tag == 'ExpressionToken': out.append(t.get('token'))
        elif t.tag == 'ExpressionVariable': out.append(name_of(t[0]))
        elif t.tag == 'ExpressionIO': out.append(name_of(t.find('pin')))
        elif t.tag == 'ExpressionWaypoint':
            w = t[0]; out.append(resolve(w).get('name') or w.get('referenceName') or '?')
        else: out.append('<%s>' % t.tag)
    s = ''.join(x if x is not None else '' for x in out)
    return re.sub(r'\s+', ' ', s).strip()

def fmt_vec(v, deg=False):
    vals = [float(x) for x in v.split(',')]
    if deg: vals = [math.degrees(x) for x in vals]
    return '[' + ', '.join('%.2f' % x for x in vals) + ']'

def waypoint(w):
    w = resolve(w)
    s = 'WP %s type=%s' % (w.get('name'), w.get('type'))
    if w.get('type') == 'Variable' and w.find('variable') is not None:
        s = 'WP Variable(%s)' % name_of(w.find('variable'))
    mp = w.find('motionParameters')
    if mp is not None and len(mp.attrib):
        s += ' ' + ' '.join('%s=%s' % kv for kv in sorted(mp.attrib.items()))
    pos = w.find('position')
    if pos is not None:
        ja = pos.find('JointAngles')
        if ja is not None: s += ' q=' + fmt_vec(ja.get('angles'), True)
        tcp = pos.find('TCPOffset')
        if tcp is not None and tcp.get('pose') != '0.0, 0.0, 0.0, 0.0, 0.0, 3.141592653589793':
            s += ' tcp=' + fmt_vec(tcp.get('pose'))
    b = w.find('BaseToFeature')
    if b is not None and b.get('pose') != '0.0, 0.0, 0.0, 0.0, 0.0, 0.0':
        s += ' feat=' + fmt_vec(b.get('pose'))
    return s

SKIP = {'kinematics', 'Kinematics', 'motionParameters', 'position', 'BaseToFeature', 'expression',
        'variable', 'pin', 'tcp', 'feature', 'initializeExpression'}

def attrs(el, drop=()):
    return ' '.join('%s=%s' % (k, v) for k, v in el.attrib.items() if k not in drop and k not in ('reference', 'class'))

def walk(el, depth, out, tag=None):
    el = resolve(el)
    ind = '  ' * depth
    tag = tag or el.tag
    kids = el.find('children')
    line = None
    if tag == 'Folder': line = 'Folder "%s"' % el.get('name')
    elif tag == 'Comment': line = '# ' + (el.get('comment') or '')
    elif tag == 'If':
        t = el.get('type')
        line = {'If': 'if', 'ElseIf': 'elif', 'Else': 'else'}[t] + (' ' + expr(el.find('expression')) if t != 'Else' else '') + (' [continuous]' if el.get('checkContinuously') == 'true' else '')
    elif tag == 'Loop':
        line = 'loop %s %s' % (el.get('type'), expr(el.find('expression')) or el.get('count') or '')
        line += ' [continuous]' if el.get('checkContinuously') == 'true' else ''
    elif tag == 'Assignment':
        line = '%s := %s' % (name_of(el.find('variable')), expr(el.find('expression')) if el.get('valueSource') == 'Expression' else '<%s>' % el.get('valueSource'))
    elif tag == 'Wait':
        if el.get('type') == 'Sleep': line = 'wait %ss' % el.findtext('waitTime')
        elif el.get('type') == 'Condition': line = 'wait until ' + expr(el.find('expression'))
        else:
            line = 'wait %s %s' % (el.get('type'), etree.tostring(el, encoding=str)[:200])
            pin = el.find('pin')
            if pin is not None: line = 'wait %s %s=%s' % (el.get('type'), name_of(pin), el.findtext('digitalValue') or el.findtext('analogValue'))
    elif tag == 'Set':
        pin = el.find('pin')
        val = el.findtext('digitalValue') or el.findtext('analogValue') or expr(el.find('expression'))
        line = 'set %s %s = %s' % (el.get('type'), name_of(pin) if pin is not None else '', val)
        if el.find('tcp') is not None: line += ' tcp=' + name_of(el.find('tcp'))
    elif tag == 'Timer': line = 'timer %s %s' % (el.get('action'), name_of(el.find('variable')))
    elif tag == 'Move':
        line = 'Move %s' % attrs(el, ('optiMoveSpeed', 'optiMoveAcceleration'))
        if el.find('tcp') is not None: line += ' tcp=' + name_of(el.find('tcp'))
        if el.find('feature') is not None: line += ' feat=' + name_of(el.find('feature'))
    elif tag == 'Waypoint': line = waypoint(el)
    elif tag == 'Script':
        if el.get('type') == 'Line': line = 'script: ' + expr(el.find('expression'))
        else:
            line = 'script %s:' % el.get('type')
            for l in (el.findtext('cachedContents') or '').splitlines():
                out.append(ind + '  | ' + l.rstrip())
            out.insert(len(out) - len((el.findtext('cachedContents') or '').splitlines()), ind + line)
            line = None
    elif tag == 'CallSubProgram':
        sp = resolve(el.find('subprogram'))
        line = 'call %s' % sp.get('name')
        out.append(ind + line)
        return  # subprogram body printed once at definition
    elif tag == 'Force':
        line = 'Force %s feat=%s sel=%s wrench=%s limF=%s limM=%s' % (el.get('type'), name_of(el.find('feature')),
            el.find('selection').get('value'), el.find('wrench').get('value'), el.find('limitsForce').get('value'), el.find('limitsMotion').get('value'))
    elif tag == 'Popup': line = 'popup %s' % attrs(el)
    elif tag == 'Halt': line = 'halt'
    elif tag == 'SuppressedNode':
        sub = []
        sn = el.find('suppressedNode')
        walk(sn, 0, sub, tag=sn.get('class'))
        for l in sub: out.append(ind + '//SUPPRESSED ' + l)
        return
    elif tag == 'Event': line = 'event on ' + expr(el.find('expression'))
    elif tag == 'Thread': line = 'Thread %s' % attrs(el)
    elif tag in ('MainProgram', 'SpecialSequence', 'InitVariablesNode'):
        line = '%s %s' % (tag, attrs(el))
        if tag == 'InitVariablesNode':
            out.append(ind + line)
            for v in el.find('variables'):
                out.append(ind + '  init %s = %s' % (v.get('name'), expr(v.find('expression'))))
            return
    elif tag == 'Until':
        line = 'until %s %s' % (attrs(el), el.findtext('Distance') or expr(el.find('expression')) or '')
    elif tag == 'subprogram' or tag == 'SubProgram': line = 'SubProgram %s' % attrs(el)
    else:
        a = attrs(el)
        extra = []
        for c in el:
            if c.tag in ('children',): continue
            if c.tag == 'expression': extra.append('expr=' + expr(c))
            elif c.tag in ('feature', 'tcp', 'pin', 'variable'): extra.append('%s=%s' % (c.tag, name_of(c)))
            elif c.text and c.text.strip(): extra.append('%s=%s' % (c.tag, c.text.strip()))
            elif c.attrib: extra.append('%s(%s)' % (c.tag, attrs(c)))
        line = '%s %s %s' % (tag.split('.')[-1], a, ' '.join(extra))
    if line is not None: out.append(ind + line.rstrip())
    if kids is not None:
        for c in kids: walk(c, depth + 1, out)
    if tag == 'Move' or tag.endswith('MoveDirectionNode'):
        pass

def convert(path):
    root = load(path)
    out = []
    kids = root.find('children')
    for c in kids: walk(c, 0, out)
    # emit subprogram definitions once
    subs = {}
    for cs in root.iter('CallSubProgram'):
        sp = resolve(cs.find('subprogram'))
        if sp.get('name') not in subs:
            body = []
            for c in sp.find('children'): walk(c, 1, body)
            subs[sp.get('name')] = body
    for n in sorted(subs):
        out.append('def %s:' % n)
        out.extend(subs[n])
    return out

if __name__ == '__main__':
    print('\n'.join(convert(sys.argv[1])))
