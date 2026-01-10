const chainForms = document.querySelectorAll('[data-chain-form]');
const chainLists = document.querySelectorAll('[data-chain-list]');
const libraryCards = document.querySelectorAll('[data-screen-card]');

const dragState = {
  screenId: null,
  screenName: null,
  screenDuration: null,
  sourceList: null,
  draggedItem: null,
  sourceType: null,
};

const buildChainItem = (screenId, screenName, screenDuration) => {
  const item = document.createElement('div');
  item.className = 'chain-item';
  item.setAttribute('draggable', 'true');
  item.setAttribute('data-screen-id', screenId);
  item.innerHTML = `
    <div>
      <div class="chain-item__title"></div>
      <div class="chain-item__meta"></div>
    </div>
    <button class="chain-item__remove" type="button" aria-label="Remove screen">×</button>
  `;
  item.querySelector('.chain-item__title').textContent = screenName;
  item.querySelector('.chain-item__meta').textContent = `${screenDuration}s`;
  return item;
};

const syncChainIds = (list) => {
  const form = list.closest('form');
  if (!form) {
    return;
  }
  const ids = Array.from(list.querySelectorAll('.chain-item')).map((item) => item.dataset.screenId);
  const hidden = form.querySelector('[data-chain-ids]');
  if (hidden) {
    hidden.value = ids.join(',');
  }
};

const updateEmptyState = (list) => {
  const empty = list.querySelector('.chain-empty');
  const hasItems = list.querySelector('.chain-item');
  if (hasItems && empty) {
    empty.remove();
  } else if (!hasItems && !empty) {
    const placeholder = document.createElement('div');
    placeholder.className = 'chain-empty';
    placeholder.textContent = 'Drop screens here to build a playlist.';
    list.appendChild(placeholder);
  }
};

const startDrag = (event, payload) => {
  dragState.screenId = payload.screenId;
  dragState.screenName = payload.screenName;
  dragState.screenDuration = payload.screenDuration;
  dragState.sourceList = payload.sourceList;
  dragState.draggedItem = payload.draggedItem || null;
  dragState.sourceType = payload.sourceType;
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', payload.screenId);
};

libraryCards.forEach((card) => {
  card.addEventListener('dragstart', (event) => {
    startDrag(event, {
      screenId: card.dataset.screenId,
      screenName: card.dataset.screenName,
      screenDuration: card.dataset.screenDuration,
      sourceType: 'library',
    });
  });
});

chainLists.forEach((list) => {
  list.addEventListener('dragstart', (event) => {
    const item = event.target.closest('.chain-item');
    if (!item) {
      return;
    }
    const meta = item.querySelector('.chain-item__meta');
    startDrag(event, {
      screenId: item.dataset.screenId,
      screenName: item.querySelector('.chain-item__title')?.textContent || 'Screen',
      screenDuration: meta ? meta.textContent.replace('s', '') : '15',
      sourceList: list.dataset.oledChannel,
      draggedItem: item,
      sourceType: 'chain',
    });
  });

  list.addEventListener('dragover', (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  });

  list.addEventListener('drop', (event) => {
    event.preventDefault();
    if (!dragState.screenId) {
      return;
    }
    const targetItem = event.target.closest('.chain-item');
    const existing = Array.from(list.querySelectorAll('.chain-item')).find(
      (item) => item.dataset.screenId === dragState.screenId
    );
    const sameList = dragState.sourceList === list.dataset.oledChannel;

    if (dragState.sourceType === 'chain' && sameList && dragState.draggedItem) {
      if (targetItem && targetItem !== dragState.draggedItem) {
        list.insertBefore(dragState.draggedItem, targetItem);
      } else {
        list.appendChild(dragState.draggedItem);
      }
    } else if (!existing) {
      const newItem = buildChainItem(
        dragState.screenId,
        dragState.screenName,
        dragState.screenDuration
      );
      if (targetItem) {
        list.insertBefore(newItem, targetItem);
      } else {
        list.appendChild(newItem);
      }
    }

    updateEmptyState(list);
    syncChainIds(list);
  });

  list.addEventListener('click', (event) => {
    const removeButton = event.target.closest('.chain-item__remove');
    if (!removeButton) {
      return;
    }
    const item = removeButton.closest('.chain-item');
    if (item) {
      item.remove();
      updateEmptyState(list);
      syncChainIds(list);
    }
  });

  updateEmptyState(list);
  syncChainIds(list);
});

chainForms.forEach((form) => {
  form.addEventListener('submit', () => {
    const list = form.querySelector('[data-chain-list]');
    if (list) {
      syncChainIds(list);
    }
  });
});

document.addEventListener('dragend', () => {
  dragState.screenId = null;
  dragState.screenName = null;
  dragState.screenDuration = null;
  dragState.sourceList = null;
  dragState.draggedItem = null;
  dragState.sourceType = null;
});
