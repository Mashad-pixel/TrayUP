(function () {
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);

 let categories=trayStorage.get("trayup-admin-categories",["Breakfast","Lunch","Meals","Snacks","Drinks","Desserts","Fast Food"]);
 const content=document.querySelector(".admin-content");
 content.innerHTML=`<div style="display:flex;justify-content:space-between"><h1 class="admin-title">Categories</h1><button class="btn btn-primary" id="add-category">Add category</button></div><div class="card table-card" style="margin-top:22px"><table class="data-table"><thead><tr><th>Name</th><th>Visibility</th><th>Actions</th></tr></thead><tbody id="category-body"></tbody></table></div>`;
 function render(){trayStorage.set("trayup-admin-categories",categories);document.getElementById("category-body").innerHTML=categories.map((name,i)=>`<tr><td><strong>${esc(name)}</strong></td><td><span class="status">Visible</span></td><td><button class="btn btn-secondary" data-edit="${Number(i)}">Rename</button> <button class="btn" data-delete="${Number(i)}" style="color:var(--danger)">Delete</button></td></tr>`).join("");}
 content.addEventListener("click",e=>{const add=e.target.closest("#add-category"),edit=e.target.closest("[data-edit]"),remove=e.target.closest("[data-delete]");if(add){const name=prompt("Category name");if(name){categories.push(name);render();}}if(edit){const name=prompt("Category name",categories[Number(edit.dataset.edit)]);if(name){categories[Number(edit.dataset.edit)]=name;render();}}if(remove&&confirm("Delete category?")){categories.splice(Number(remove.dataset.delete),1);render();}});
 render();
})();
