const file = document.getElementById("file");
const sel = id => document.getElementById(id);
file.onchange = async () => {
  const lines = (await file.files[0].text()).split(/\r?\n/).filter(Boolean);
  const head = lines[0].split(",").map(h => h.trim());
  for (const id of ["target", "site_col", "group_col"]) {
    sel(id).innerHTML = id === "group_col" ? '<option value="">None</option>' : "";
    head.forEach(h => sel(id).add(new Option(h, h)));
  }
  const sites = () => {
    const i = head.indexOf(sel("site_col").value);
    const vals = [...new Set(lines.slice(1).map(r => r.split(",")[i]))].slice(0, 40);
    sel("dev_site").innerHTML = "";
    vals.forEach(v => sel("dev_site").add(new Option(v, v)));
  };
  sel("site_col").onchange = sites;
  sites();
};
