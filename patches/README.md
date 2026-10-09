# Фиксы в стороннем коде

## ai-toolkit: падение тренера LoRA на не-строковом промпте

**Где:** `extensions_built_in/diffusion_models/<model>/src/text_encoder.py`

**Симптом:** обучение character-LoRA падает на старте:

```
TypeError: unsupported operand type(s) for +: 'bool' and 'str'
```

**Причина:** энкодер конкатенирует шаблон с промптом без проверки типа:

```python
text = PROMPT_TEMPLATE_ENCODE_PREFIX + prompt
```

Когда в датасете у части изображений пустая подпись, по ветке загрузки сюда
приходит `False` вместо строки, и сложение `bool + str` валит процесс.

**Фикс** — приведение к строке перед конкатенацией:

```diff
+    if not isinstance(prompt, str):
+        prompt = ""
     text = PROMPT_TEMPLATE_ENCODE_PREFIX + prompt
```

**Контекст обучения, на котором ловилось:** база bf16, network dim 32, lr 1e-4,
авто-каптионинг BLIP, ~3000 шагов, датасет 180+ изображений. Часть подписей
оказывалась пустой после фильтрации — на таком датасете падение воспроизводится
стабильно, на полностью подписанном не проявляется.
