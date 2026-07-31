const root = document.querySelector("[data-concept-discovery]");

if (root) {
  const input = root.querySelector("[data-concept-input]");
  const selected = root.querySelector("[data-concept-id]");
  const listbox = root.querySelector("[data-concept-listbox]");
  const status = root.querySelector("[data-concept-status]");
  const options = Array.from(listbox.querySelectorAll("[role='option']"));
  let visibleOptions = [...options];
  let activeIndex = -1;

  const setExpanded = (expanded) => {
    input.setAttribute("aria-expanded", String(expanded));
    listbox.hidden = !expanded;
  };

  const setActive = (index) => {
    if (!visibleOptions.length) return;
    activeIndex = (index + visibleOptions.length) % visibleOptions.length;
    options.forEach((option) => {
      option.setAttribute(
        "aria-selected",
        String(option === visibleOptions[activeIndex]),
      );
    });
    input.setAttribute("aria-activedescendant", visibleOptions[activeIndex].id);
    visibleOptions[activeIndex].scrollIntoView({ block: "nearest" });
  };

  const choose = (option) => {
    selected.value = option.dataset.conceptId;
    input.value = option.dataset.preferredName;
    status.textContent = `Selected ${option.dataset.preferredName}, canonical identifier ${option.dataset.conceptId}.`;
    setExpanded(false);
  };

  options.forEach((option) => {
    option.addEventListener("mousedown", (event) => {
      event.preventDefault();
      choose(option);
    });
  });

  input.addEventListener("input", () => {
    selected.value = "";
    const query = input.value.trim();
    const normalized = query.toLocaleLowerCase();
    visibleOptions = options.filter((option) => {
      const matches = option.textContent.toLocaleLowerCase().includes(normalized);
      option.hidden = !matches;
      return matches;
    });
    activeIndex = -1;
    input.removeAttribute("aria-activedescendant");
    status.textContent = `${visibleOptions.length} medicine ${visibleOptions.length === 1 ? "option" : "options"} available. Submit Find medicines to search again.`;
    setExpanded(Boolean(query) && visibleOptions.length > 0);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setExpanded(visibleOptions.length > 0);
      setActive(activeIndex + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      choose(visibleOptions[activeIndex]);
    } else if (event.key === "Escape") {
      setExpanded(false);
      input.removeAttribute("aria-activedescendant");
    }
  });

  input.addEventListener("blur", () => {
    window.setTimeout(() => setExpanded(false), 100);
  });
}
