const sel = id => document.getElementById(id);
const file = sel("file");
let columns = [];
const fill = (id, items, blank) => {
  sel(id).innerHTML = blank ? '<option value="">None</option>' : "";
  items.forEach(v => sel(id).add(new Option(v, v)));
};
const guess = (names, re) => names.find(n => re.test(n)) || names[0];
function sites() {
  const c = columns.find(x => x.name === sel("site_col").value);
  fill("dev_site", c && c.values ? c.values : []);
}
file.onchange = async () => {
  const body = new FormData();
  body.append("file", file.files[0]);
  const r = await fetch("/inspect", { method: "POST", body });
  if (!r.ok) {
    sel("msg").textContent = "That file could not be read as a CSV.";
    return;
  }
  const info = await r.json();
  columns = info.columns;
  const names = columns.map(c => c.name);
  const grouped = columns.filter(c => c.values).map(c => c.name);
  fill("target", names);
  fill("site_col", grouped.length ? grouped : names);
  fill("group_col", grouped, true);
  sel("target").value = guess(names, /outcome|target|label|disease|^num$|^y$/i);
  sel("site_col").value = guess(grouped, /site|hospital|center|centre|cohort/i);
  sel("msg").textContent = info.rows + " rows read. Check the selections below.";
  sel("site_col").onchange = sites;
  sites();
};
