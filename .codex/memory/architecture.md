# Architecture

## Эпизод и выбранный файл раздачи

**Component** — Episode Matcher, Playback Resolver, Episode Navigation.

**Fact** — Логический эпизод определяется сериалом, сезоном и номером серии. Физический файл определяется парой `task_id` и `file_id`. Playback Resolver для сериала использует сохранённую связь между ними. `selected_file_id` обозначает текущий выбор файла в torrent-задаче. Episode Matcher сохраняет новую связь автоматически, только если для каждого затронутого эпизода есть единственное точное совпадение (`exact`) среди файлов этой раздачи и эпизод ещё не привязан к другому файлу в ней.

**Reason** — Одна раздача может содержать несколько эпизодов, а у эпизода могут быть разные варианты. Если соседние эпизоды находятся в одном файле, для точного автоперехода нужны временные границы.

**Sources** — [backend/app/services/episodes/matcher.py](../../backend/app/services/episodes/matcher.py#L115), [backend/app/models/episodes.py](../../backend/app/models/episodes.py#L18), [backend/app/services/playback/resolver.py](../../backend/app/services/playback/resolver.py#L64), [backend/app/services/playback/navigation.py](../../backend/app/services/playback/navigation.py#L47).

## Смена идентификатора при резервной загрузке карточки

**Component** — CatalogService, Android TV.

**Fact** — При недоступности TMDB запрос деталей с названием из карточки может вернуть объект Кинопоиска с ID из зарезервированного диапазона KADR. Сервер проверяет тип и точное совпадение нормализованного названия, а при переданном годе проверяет и год. После успешного ответа Android TV принимает возвращённый ID как актуальный идентификатор карточки для запросов сезонов, источников и воспроизведения.

**Reason** — ID определяет, к какому провайдеру обратится сервер. Повторное использование исходного TMDB ID снова направит запрос к недоступному провайдеру.

**Sources** — [backend/app/services/metadata/catalog.py](../../backend/app/services/metadata/catalog.py#L215), [android-tv/app/src/main/java/ru/kadr/tv/MainViewModel.kt](../../android-tv/app/src/main/java/ru/kadr/tv/MainViewModel.kt#L163).
