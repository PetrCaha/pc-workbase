'use strict';
(() => {
  const t = window.gettext || (value => value);
  const lang = document.documentElement.lang;
  const date = value => value ? new Intl.DateTimeFormat(lang).format(new Date(value + 'T12:00:00')) : '—';
  const money = value => new Intl.NumberFormat(lang, {style:'currency',currency:'CZK'}).format(Number(value));
  function item(grid, label, value) {
    const cell = document.createElement('div');
    const name = document.createElement('span'); name.textContent=t(label);
    const text = document.createElement('strong'); text.textContent=value || '—';
    cell.append(name,text);grid.append(cell);
  }
  document.querySelectorAll('.preview-button').forEach(button => button.addEventListener('click', async () => {
    const row=document.getElementById(button.getAttribute('aria-controls'));
    const opening=button.getAttribute('aria-expanded') !== 'true';
    document.querySelectorAll('.preview-button').forEach(other => {
      other.setAttribute('aria-expanded','false');
      document.getElementById(other.getAttribute('aria-controls')).hidden=true;
    });
    if(!opening)return;
    button.setAttribute('aria-expanded','true');row.hidden=false;
    const content=row.querySelector('.quick-content');content.textContent=t('Načítám…');
    try {
      const response=await fetch(`/api/${button.dataset.kind}/${button.dataset.id}/`, {headers:{Accept:'application/json'}});
      if(!response.ok || !response.headers.get('content-type')?.includes('application/json'))throw new Error();
      const data=await response.json();
      const grid=document.createElement('div');grid.className='quick-grid';
      if(button.dataset.kind==='customers') {
        item(grid,'Zákazník',data.name);item(grid,'Adresa',[data.street,data.city].filter(Boolean).join(', '));
        item(grid,'Hlavní kontakt',data.main_contact?.name);item(grid,'E-mail',data.main_contact?.email || data.email);
        item(grid,'Otevřené zakázky',String(data.open_jobs_count));
      } else {
        item(grid,'Zakázka',data.title);item(grid,'Zákazník',data.customer_name);item(grid,'Odpovědná osoba',data.responsible_name);
        item(grid,'Stav',data.status_label);item(grid,'Termín',date(data.due_date));item(grid,'Cena',money(data.price));
      }
      content.replaceChildren(grid);
      if(data.description){const p=document.createElement('p');p.className='quick-description';p.textContent=data.description;content.append(p);}
    } catch {content.textContent=t('Náhled se nepodařilo načíst. Obnovte stránku nebo otevřete detail.');}
  }));
  const customer=document.querySelector('#id_customer'),contact=document.querySelector('#id_contact');
  let controller;
  if(customer && contact && !customer.disabled)customer.addEventListener('change',async()=>{
    controller?.abort();controller=new AbortController();
    contact.replaceChildren(new Option('—',''));if(!customer.value)return;
    try {
      const response=await fetch(`/api/contacts/?customer=${encodeURIComponent(customer.value)}`,{signal:controller.signal});
      if(!response.ok)throw new Error();
      const contacts=await response.json();
      contacts.forEach(person=>contact.append(new Option(`${person.name} — ${person.role_label}`,person.id)));
    } catch(error) {
      if(error.name==='AbortError')return;
      const message=document.createElement('p');message.setAttribute('role','status');message.textContent=t('Kontakty se nepodařilo načíst. Obnovte stránku a zkuste to znovu.');contact.after(message);
    }
  });
  document.querySelector('#form-result')?.focus();
})();
