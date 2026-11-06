// Generates sample data for Keel Budget (May 2026 to Nov 5 2026).
// Writes settings.json, m-YYYY-MM.json files, and local.json (combined) to the out dir.
const fs = require('fs');
const path = require('path');
const out = process.argv[2];
fs.mkdirSync(out, { recursive: true });

let seed = 42;
const rnd = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
const between = (a, b) => Math.round((a + rnd() * (b - a)) * 100) / 100;
const pick = arr => arr[Math.floor(rnd() * arr.length)];
const pad = n => String(n).padStart(2, '0');
let idn = 0;
const id = p => p + (++idn).toString(36) + Math.floor(rnd() * 1e6).toString(36);

const groups = [
  { id: 'income', name: 'Income', type: 'income' },
  { id: 'bills', name: 'Bills', type: 'expense' },
  { id: 'everyday', name: 'Everyday', type: 'expense' },
  { id: 'other', name: 'Other', type: 'expense' },
  { id: 'transfers', name: 'Transfers', type: 'transfer' },
];
const ESSENTIAL = new Set(['rent', 'utilities', 'phone', 'insurance', 'carpay', 'groceries', 'gas', 'transit', 'health']);
const categories = [
  ['paycheck', 'Paychecks', 'income'], ['freelance', 'Freelance income', 'income'], ['otherinc', 'Other income', 'income'], ['interest', 'Interest', 'income'],
  ['rent', 'Rent', 'bills'], ['utilities', 'Utilities', 'bills'], ['phone', 'Phone & internet', 'bills'],
  ['insurance', 'Insurance', 'bills'], ['subs', 'Subscriptions', 'bills'], ['carpay', 'Car payment', 'bills'],
  ['groceries', 'Groceries', 'everyday'], ['dining', 'Restaurants', 'everyday'], ['coffee', 'Coffee', 'everyday'],
  ['gas', 'Gas', 'everyday'], ['transit', 'Transit & rides', 'everyday'], ['shopping', 'Shopping', 'everyday'],
  ['fun', 'Entertainment', 'everyday'], ['health', 'Health & fitness', 'everyday'], ['personal', 'Personal care', 'everyday'],
  ['travel', 'Travel', 'everyday'], ['gifts', 'Gifts & donations', 'everyday'], ['home', 'Home', 'everyday'],
  ['uncat', 'Uncategorized', 'other'], ['fees', 'Fees', 'other'],
  ['transfer', 'Transfer', 'transfers'], ['ccpay', 'Credit card payment', 'transfers'],
  ['reimb', 'Reimbursement received', 'transfers'], ['settle', 'Partner settle-up', 'transfers'],
].map(([cid, name, group]) => ({ id: cid, name, group, essential: ESSENTIAL.has(cid) }));
categories.find(c => c.id === 'dining').rollover = true; categories.find(c => c.id === 'dining').rolloverStart = '2026-09';
categories.find(c => c.id === 'shopping').rollover = true; categories.find(c => c.id === 'shopping').rolloverStart = '2026-09';

const accounts = [
  { id: 'chk', name: 'Everyday Checking', type: 'checking', institution: 'Harbor Credit Union', balance: 0, history: {} },
  { id: 'sav', name: 'High-Yield Savings', type: 'savings', institution: 'Harbor Credit Union', balance: 0, history: {} },
  { id: 'card', name: 'Rewards Visa', type: 'credit', institution: 'Summit Bank', balance: 0, history: {}, apr: 24.99, minPayment: 35, dueDay: 22, rewards: { base: 1.5, bonus: [{ cat: 'dining', rate: 3 }, { cat: 'travel', rate: 2 }] } },
  { id: 'card2', name: "Grocer's Choice Mastercard", type: 'credit', institution: 'Meadow Bank', balance: 0, history: {}, apr: 21.49, minPayment: 25, dueDay: 12, rewards: { base: 1, bonus: [{ cat: 'groceries', rate: 4 }, { cat: 'gas', rate: 3 }] } },
  { id: 'k401', name: '401(k)', type: 'investment', institution: 'Brightwater Retirement', balance: 0, history: {} },
  { id: 'brk', name: 'Brokerage', type: 'investment', institution: 'Brightwater Invest', balance: 0, history: {} },
  { id: 'car', name: 'Auto Loan', type: 'loan', institution: 'Summit Bank', balance: 0, history: {}, apr: 6.4, minPayment: 389 },
];
const start = { chk: 1210.22, sav: 14250, card: -980.4, card2: 0 };

const months = ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10', '2026-11'];
const lastDay = { '2026-11': 5 };
const dim = ym => new Date(+ym.slice(0, 4), +ym.slice(5, 7), 0).getDate();
const txByMonth = {};
const add = (date, merchant, amount, categoryId, accountId, notes, extra) => {
  const ym = date.slice(0, 7);
  const t = { id: id('t'), date, merchant, amount: Math.round(amount * 100) / 100, categoryId, accountId, notes: notes || '', ...(extra || {}) };
  (txByMonth[ym] = txByMonth[ym] || []).push(t);
  return t;
};
const SHARED = { shared: true, paidBy: 'me' };

// Biweekly paychecks starting Fri May 8 2026
for (let d = new Date(2026, 4, 8, 12); d <= new Date(2026, 10, 5, 12); d.setDate(d.getDate() + 14)) {
  const ds = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  add(ds, 'Northwind Logistics Payroll', 2840.16, 'paycheck', 'chk');
}

const groceries = ['Greenleaf Market', 'Greenleaf Market', 'Fresh Fields Grocery', 'Corner Pantry'];
const dining = ['Corner Bistro', 'Pho Garden', 'Slice House Pizza', 'Taqueria Luna', 'Noodle Bar 88', 'The Copper Grill'];
const coffee = ['Bean & Barrel Coffee', 'Bean & Barrel Coffee', 'Morning Ritual Cafe'];
const shopping = ['Parcel Depot Online', 'Hartwell Home Goods', 'Threadline Apparel', 'Bookworm & Co'];
const fun = ['Starlight Cinema', 'Riverside Bowling', 'Ticket Hall', 'Arcadia Games'];

months.forEach((ym, mi) => {
  const last = lastDay[ym] || dim(ym);
  const day = n => ym + '-' + pad(n);
  const has = n => n <= last;
  if (has(1)) add(day(1), 'Maple Court Apartments', -1950, 'rent', 'chk', '', SHARED);
  if (has(3)) add(day(3), 'IronWorks Gym', -49, 'health', 'card');
  if (has(8)) add(day(8), 'Lumen Wireless', -85, 'phone', 'card');
  if (has(11)) add(day(11), 'Streamly', ym >= '2026-10' ? -17.99 : -15.49, 'subs', 'card');
  if (has(12)) add(day(12), 'SoundWave Music', -10.99, 'subs', 'card');
  if (has(14)) add(day(14), 'City Power & Light', -between(96, 168), 'utilities', 'chk');
  if (has(15)) add(day(15), 'Summit Bank Auto Loan', -389, 'carpay', 'chk');
  if (has(20)) add(day(20), 'FiberNet Internet', -70, 'phone', 'card', '', SHARED);
  if (has(24)) add(day(24), 'Guardian Auto Insurance', -142, 'insurance', 'chk');
  if (has(28)) add(day(28), 'Transfer to High-Yield Savings', -1000, 'transfer', 'chk');
  if (has(28)) add(day(28), 'Transfer from Everyday Checking', 1000, 'transfer', 'sav');
  if (has(27)) add(day(27), 'Harbor CU Interest', between(38, 46), 'interest', 'sav');
  // Pay the card on the 22nd: roughly last month's spend
  for (let n = 1; n <= last; n++) {
    const r = rnd();
    if (n % 4 === 2) { const g = pick(groceries); add(day(n), g, -between(42, 138), 'groceries', 'card', '', g === 'Greenleaf Market' ? SHARED : null); }
    if (r < 0.32) add(day(n), pick(dining), -between(14, 68), 'dining', 'card');
    if (r > 0.55 && r < 0.85) add(day(n), pick(coffee), -between(4.25, 9.8), 'coffee', 'card');
    if (n % 9 === 5) add(day(n), 'Northside Fuel', -between(38, 61), 'gas', ym >= '2026-09' ? 'card2' : 'card');
    if (r > 0.9) add(day(n), pick(shopping), -between(18, 140), 'shopping', 'card');
    if (n === 18 || n === 6) add(day(n), 'Metro Transit', -between(12, 30), 'transit', 'card');
    if (n === 16 && rnd() > 0.3) add(day(n), pick(fun), -between(22, 85), 'fun', 'card');
    if (n === 10 && rnd() > 0.5) add(day(n), 'Clearview Pharmacy', -between(9, 42), 'health', 'card');
    if (n === 25 && rnd() > 0.4) add(day(n), 'Shear Genius Salon', -between(35, 70), 'personal', 'card');
  }
});
// Freelance side income, irregular
add('2026-06-09', 'Brightline Studio', 640, 'freelance', 'chk', 'Logo project');
add('2026-07-18', 'Brightline Studio', 1380, 'freelance', 'chk', 'Website refresh');
add('2026-08-12', 'Brightline Studio', 420, 'freelance', 'chk');
add('2026-09-25', 'Brightline Studio', 950, 'freelance', 'chk');
add('2026-10-14', 'Brightline Studio', 300, 'freelance', 'chk');
// Partner-paid shared costs (no account of yours)
add('2026-07-19', 'Warehouse Club (Jordan paid)', -186.4, 'groceries', '', '', { shared: true, paidBy: 'partner' });
add('2026-09-06', 'Hardware store (Jordan paid)', -64, 'home', '', '', { shared: true, paidBy: 'partner' });
add('2026-10-11', 'Warehouse Club (Jordan paid)', -212.75, 'groceries', '', '', { shared: true, paidBy: 'partner' });
// Reimbursements
const conf = add('2026-09-15', 'Harborview Hotel', -289, 'travel', 'card', 'Conference hotel', { reimb: { from: 'Northwind Logistics', amount: 289, status: 'pending', since: '2026-09-15' } });
const paid = add('2026-09-30', 'Northwind Expense Reimbursement', 289, 'reimb', 'chk', '', { reimbFor: conf.id });
conf.reimb.status = 'paid'; conf.reimb.paidId = paid.id; conf.reimb.paidDate = '2026-09-30';
add('2026-09-29', 'Skyway Airlines', -412.6, 'travel', 'card', 'Client visit flight', { reimb: { from: 'Northwind Logistics', amount: 412.6, status: 'pending', since: '2026-09-29' } });
add('2026-10-21', 'Clearview Pharmacy', -42, 'health', 'card', 'Prescription', { reimb: { from: 'HSA', amount: 42, status: 'pending', since: '2026-10-21' } });
// Possible free trials
add('2026-10-20', 'Pixelbox Pro', -1, 'subs', 'card');
add('2026-11-02', 'FitTrack Plus', 0, 'subs', 'card');
// One-offs
add('2026-06-14', 'Skyway Airlines', -486.4, 'travel', 'card', 'Flights for August wedding');
add('2026-08-09', 'Lakeside Inn', -612.0, 'travel', 'card');
add('2026-08-10', 'Hartwell Home Goods', -129.99, 'gifts', 'card', 'Wedding gift');
add('2026-07-04', 'Ridgeline Outfitters', -214.5, 'shopping', 'card');
add('2026-09-19', 'Marketplace Sale', 180, 'otherinc', 'chk', 'Sold old bike');
add('2026-10-02', 'Hartwell Home Goods', -342.18, 'home', 'card', 'New desk chair');
add('2026-10-31', 'Party City Supply', -46.2, 'uncat', 'card');
add('2026-11-04', 'Venmo Cashout', 62.5, 'uncat', 'chk');
add('2026-09-30', 'Animal Rescue League', -50, 'gifts', 'card');

// Card payments cover the previous month's card spending
const payCard = (acct, dayN, label) => months.forEach((ym, mi) => {
  if (mi === 0 || (lastDay[ym] || 31) < dayN) return;
  const prev = months[mi - 1];
  const spend = -(txByMonth[prev] || []).filter(t => t.accountId === acct && t.categoryId !== 'ccpay').reduce((s, t) => s + t.amount, 0);
  const amt = Math.round(spend * 100) / 100; if (amt <= 0) return;
  add(ym + '-' + pad(dayN), 'Payment to ' + label, -amt, 'ccpay', 'chk');
  add(ym + '-' + pad(dayN), 'Payment from Everyday Checking', amt, 'ccpay', acct);
});
payCard('card', 22, 'Rewards Visa');
payCard('card2', 12, "Grocer's Choice Mastercard");
// Jordan settles their 40% share on the 2nd of the next month
const MINE = 0.6;
months.forEach((ym, mi) => {
  if (mi === 0 || (lastDay[ym] || 31) < 2) return;
  let owed = 0;
  for (const t of txByMonth[months[mi - 1]] || []) if (t.shared && t.amount < 0) owed += t.paidBy === 'partner' ? t.amount * MINE : -t.amount * (1 - MINE);
  owed = Math.round(owed * 100) / 100; if (!owed) return;
  add(ym + '-02', owed > 0 ? 'Zelle from Jordan' : 'Zelle to Jordan', owed, 'settle', 'chk', 'Shared costs for ' + months[mi - 1]);
});
for (const ym of Object.keys(txByMonth)) txByMonth[ym].sort((a, b) => b.date.localeCompare(a.date));

// Balances: walk months forward for chk/sav/card
const bal = { ...start };
for (const ym of months) {
  for (const t of txByMonth[ym] || []) if (bal[t.accountId] !== undefined) bal[t.accountId] += t.amount;
  for (const k of Object.keys(start)) accounts.find(a => a.id === k).history[ym] = Math.round(bal[k] * 100) / 100;
}
const k401 = [58200, 59440, 60910, 60120, 61870, 63150, 63520];
const brk = [11800, 12260, 12890, 12410, 13020, 13660, 13540];
const car = [-13020, -12698, -12375, -12050, -11723, -11394, -11394];
months.forEach((ym, i) => {
  accounts.find(a => a.id === 'k401').history[ym] = k401[i];
  accounts.find(a => a.id === 'brk').history[ym] = brk[i];
  accounts.find(a => a.id === 'car').history[ym] = car[i];
});
for (const a of accounts) a.balance = a.history['2026-11'];

const budgetMay = {
  paycheck: 5680, interest: 40,
  freelance: 500,
  rent: 1170, utilities: 140, phone: 130, insurance: 142, subs: 30, carpay: 389,
  groceries: 430, dining: 380, coffee: 70, gas: 150, transit: 50, shopping: 200, fun: 100,
  health: 75, personal: 50, travel: 150, gifts: 50, home: 75,
};
const budgetSep = { ...budgetMay, dining: 340, shopping: 160, home: 120 };

const settings = {
  v: 1,
  sample: true,
  currency: 'USD',
  groups,
  categories,
  accounts,
  budgets: { '2026-05': budgetMay, '2026-09': budgetSep },
  goals: [
    { id: 'g1', name: 'Emergency fund', target: 20000, saved: 17450, targetDate: '2027-03-01' },
    { id: 'g2', name: 'Japan trip', target: 6000, saved: 2150, targetDate: '2027-04-15' },
    { id: 'g3', name: 'New laptop', target: 1800, saved: 1260, targetDate: '2027-01-15' },
  ],
  recurring: [
    { id: 'r1', name: 'Maple Court Apartments', amount: -1950, cadence: 'monthly', anchor: '2026-05-01', categoryId: 'rent', accountId: 'chk', shared: true },
    { id: 'r2', name: 'Northwind Logistics Payroll', amount: 2840.16, cadence: 'biweekly', anchor: '2026-05-08', categoryId: 'paycheck', accountId: 'chk' },
    { id: 'r3', name: 'Lumen Wireless', amount: -85, cadence: 'monthly', anchor: '2026-05-08', categoryId: 'phone', accountId: 'card' },
    { id: 'r4', name: 'Streamly', amount: -15.49, cadence: 'monthly', anchor: '2026-05-11', categoryId: 'subs', accountId: 'card' },
    { id: 'r5', name: 'City Power & Light', amount: -135, cadence: 'monthly', anchor: '2026-05-14', categoryId: 'utilities', accountId: 'chk' },
    { id: 'r6', name: 'Summit Bank Auto Loan', amount: -389, cadence: 'monthly', anchor: '2026-05-15', categoryId: 'carpay', accountId: 'chk' },
    { id: 'r7', name: 'FiberNet Internet', amount: -70, cadence: 'monthly', anchor: '2026-05-20', categoryId: 'phone', accountId: 'card', shared: true },
    { id: 'r8', name: 'Guardian Auto Insurance', amount: -142, cadence: 'monthly', anchor: '2026-05-24', categoryId: 'insurance', accountId: 'chk' },
    { id: 'r9', name: 'IronWorks Gym', amount: -49, cadence: 'monthly', anchor: '2026-05-03', categoryId: 'health', accountId: 'card' },
    { id: 'y1', name: "Renter's insurance", amount: -168, cadence: 'yearly', anchor: '2027-01-05', categoryId: 'insurance', accountId: 'chk' },
    { id: 'y2', name: 'Tax prep software', amount: -89, cadence: 'yearly', anchor: '2027-02-10', categoryId: 'fees', accountId: 'card' },
    { id: 'y3', name: 'Car registration', amount: -186, cadence: 'yearly', anchor: '2027-03-14', categoryId: 'carpay', accountId: 'chk' },
    { id: 'y4', name: 'Warehouse Club membership', amount: -65, cadence: 'yearly', anchor: '2027-06-01', categoryId: 'shopping', accountId: 'card' },
  ],
  household: { enabled: true, partnerName: 'Jordan', split: 60 },
  smoothing: { enabled: false, startBuffer: 21000, window: 12, start: null },
  trials: { fittrackplus: { days: 7 } },
  payoff: { strategy: 'avalanche', extra: 150 },
  rules: [
    { id: 'u1', match: 'greenleaf', categoryId: 'groceries' },
    { id: 'u2', match: 'bean & barrel', categoryId: 'coffee' },
    { id: 'u3', match: 'metro transit', categoryId: 'transit' },
  ],
};

fs.writeFileSync(path.join(out, 'settings.json'), JSON.stringify(settings));
const local = { settings, months: {} };
for (const ym of Object.keys(txByMonth)) {
  fs.writeFileSync(path.join(out, 'm-' + ym + '.json'), JSON.stringify({ txns: txByMonth[ym] }));
  local.months[ym] = txByMonth[ym];
}
fs.writeFileSync(path.join(out, 'local.json'), JSON.stringify(local));
const counts = Object.fromEntries(Object.entries(txByMonth).map(([k, v]) => [k, v.length]));
console.log('txn counts', counts);
console.log('balances', accounts.map(a => a.name + ' ' + a.balance).join(' | '));
console.log('settings bytes', JSON.stringify(settings).length);
