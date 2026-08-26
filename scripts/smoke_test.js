// Minimal DOM stub: enough to execute the tracker's top-level render pass and
// surface real runtime errors (undefined .map, bad field access) without a browser.
const store = {};
globalThis.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};

const made = [];
function el(id) {
  const node = {
    id,
    _html: '',
    // Real <select>s report their first selected option ("all" here); only the
    // search box starts genuinely empty.
    value: /search/i.test(id) ? '' : 'all',
    checked: false,
    textContent: '',
    dataset: {},
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    style: {},
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
    setAttribute(){}, getAttribute(){ return null; },
    addEventListener(){}, removeEventListener(){},
    appendChild(){}, querySelector(){ return null; },
    querySelectorAll(){ return []; },
    closest(){ return null; },
    focus(){}, scrollIntoView(){},
  };
  made.push(node);
  return node;
}

const byId = new Map();
globalThis.document = {
  getElementById(id) {
    if (!byId.has(id)) byId.set(id, el(id));
    return byId.get(id);
  },
  querySelector() {
    // the pressed track button in a real page carries data-filter="all"
    const n = el('q');
    n.dataset = { filter: 'all', view: 'shortlist', ip: 'behavioral' };
    return n;
  },
  querySelectorAll(){ return []; },
  addEventListener(){},
  documentElement: { setAttribute(){}, getAttribute(){ return null; },
                     classList:{add(){},remove(){},toggle(){}} },
  body: el('body'),
  createElement(){ return el('created'); },
};
globalThis.window = {
  matchMedia: () => ({ matches: false, addEventListener(){}, addListener(){} }),
  addEventListener(){}, localStorage: globalThis.localStorage,
};
globalThis.navigator = { clipboard: { writeText: async () => {} } };

// ---- run the page script -------------------------------------------------
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
try {
  new Function(src)();
} catch (e) {
  console.error('RUNTIME ERROR:', e.message);
  console.error(e.stack.split('\n').slice(0, 4).join('\n'));
  process.exit(1);
}

// ---- report what actually rendered --------------------------------------
const filled = [...byId.entries()].filter(([, n]) => n._html && n._html.length > 0);
console.log('rendered targets:', filled.length);
for (const [id, n] of filled) {
  console.log(`  #${id.padEnd(14)} ${String(n._html.length).padStart(6)} chars`);
}
const empty = ['board', 'ip-behavioral', 'rcBoard'].filter(
  id => !byId.has(id) || !byId.get(id)._html);
if (empty.length) {
  console.error('WARNING: expected-but-empty:', empty.join(', '));
  process.exit(2);
}
console.log('RUNTIME OK');

// show the roles board so we can confirm cards (not the empty state) rendered
const board = byId.get('board');
console.log('\n--- #board head ---');
console.log(board._html.slice(0, 400));
console.log('role cards:', (board._html.match(/<article class="role/g) || []).length);
