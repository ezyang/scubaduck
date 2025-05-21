
function initChipInput(filter, fetchOptions) {
  const input = filter.querySelector('.f-val');
  const chipsEl = filter.querySelector('.chip-input');
  const dropdown = filter.querySelector('.chip-dropdown');
  const copyBtn = filter.querySelector('.chip-copy');
  filter.chips = [];
  filter.renderChips = renderChips;
  filter.addChip = addChip;
  let highlight = 0;
  let dropdownLocked = false;

  chipsEl.addEventListener('click', () => {
    input.focus();
  });

    function renderChips() {
      chipsEl.querySelectorAll('.chip').forEach(c => c.remove());
      filter.chips.forEach((v, i) => {
        const span = document.createElement('span');
        span.className = 'chip';
        span.textContent = v;
        const x = document.createElement('span');
        x.className = 'x';
        x.textContent = '✖';
        x.addEventListener('click', e => {
          e.stopPropagation();
          filter.chips.splice(i, 1);
          renderChips();
          input.focus();
        });
        span.appendChild(x);
        chipsEl.insertBefore(span, input);
      });
    }

  function hideDropdown() {
    dropdown.style.display = 'none';
    dropdownLocked = true;
  }

  function showDropdown() {
    if (!dropdownLocked && document.activeElement === input) {
      dropdown.style.display = 'block';
    }
  }

  function updateHighlight() {
    Array.from(dropdown.children).forEach((c, i) => {
      c.classList.toggle('highlight', i === highlight);
    });
  }

  function addChip(val) {
    if (!val) return;
    const i = filter.chips.indexOf(val);
    if (i !== -1) {
      filter.chips.splice(i, 1);
    } else {
      filter.chips.push(val);
    }
    input.value = '';
    renderChips();
  }

  copyBtn.addEventListener('click', () => {
    navigator.clipboard && navigator.clipboard.writeText(filter.chips.join(','));
  });

  input.addEventListener('paste', e => {
    e.preventDefault();
    const text = e.clipboardData.getData('text');
    if (e.shiftKey) {
      addChip(text.trim());
    } else {
      text.split(',').forEach(t => addChip(t.trim()));
    }
    hideDropdown();
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') {
      if (dropdown.style.display !== 'none') {
        highlight = Math.min(highlight + 1, dropdown.children.length - 1);
        updateHighlight();
      }
      e.preventDefault();
    } else if (e.key === 'ArrowUp') {
      if (dropdown.style.display !== 'none') {
        highlight = Math.max(highlight - 1, 0);
        updateHighlight();
      }
      e.preventDefault();
    } else if (e.key === 'Backspace' && input.value === '') {
      if (filter.chips.length > 0) {
        filter.chips.pop();
        renderChips();
      }
    } else if (e.key === 'Enter') {
      if (dropdown.style.display !== 'none' && dropdown.children.length > 0) {
        const val = dropdown.children[highlight].dataset.value;
        if (val !== input.value.trim()) {
          addChip(val);
        } else {
          addChip(input.value.trim());
        }
      } else {
        addChip(input.value.trim());
      }
      hideDropdown();
      e.preventDefault();
    }
  });

  function renderDropdown(vals) {
    dropdown.innerHTML = '';
    const typed = input.value.trim();
    if (typed) {
      vals.splice(1, 0, typed);
    }
    vals.forEach((v, i) => {
      const d = document.createElement('div');
      d.textContent = v;
      d.dataset.value = v;
      d.addEventListener('mouseover', () => {
        highlight = i;
        updateHighlight();
      });
      d.addEventListener('mousedown', evt => {
        evt.preventDefault();
        addChip(v);
        hideDropdown();
        input.blur();
      });
      dropdown.appendChild(d);
    });
    if (vals.length) {
      highlight = 0;
      updateHighlight();
      showDropdown();
    } else {
      hideDropdown();
    }
  }

  function loadOptions() {
    dropdownLocked = false;
    if (!fetchOptions) {
      dropdown.innerHTML = '';
      return;
    }
    Promise.resolve(fetchOptions(input.value, filter)).then(values => {
      renderDropdown(Array.isArray(values) ? values : []);
    });
  }

  input.addEventListener('focus', loadOptions);
  input.addEventListener('input', loadOptions);

  document.addEventListener('click', evt => {
    if (evt.target !== input) {
      hideDropdown();
    }
  });
}
