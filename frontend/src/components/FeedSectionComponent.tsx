import type { FeedSection } from "../types";
import StoryCardComponent from "./StoryCardComponent";

const SECTION_ICONS: Record<string, string> = {
  breaking_importance: "//",
  undercovered: "??",
  deadlines: ">>",
  slow_burn: "~~",
};

interface Props {
  section: FeedSection;
  onSelectTopic: (id: string) => void;
}

export default function FeedSectionComponent({ section, onSelectTopic }: Props) {
  if (section.items.length === 0) return null;

  const icon = SECTION_ICONS[section.name] ?? "--";

  return (
    <div className="feed-section" data-section={section.name}>
      <div className="section-header">
        <span className="section-badge">{icon}</span>
        <span className="section-title">{section.display_name}</span>
        {section.description && (
          <span className="section-desc">{section.description}</span>
        )}
      </div>
      <div className="section-grid">
        {section.items.map((item) => (
          <StoryCardComponent
            key={item.card.id}
            card={item.card}
            onClick={() => onSelectTopic(item.card.id)}
          />
        ))}
      </div>
    </div>
  );
}
