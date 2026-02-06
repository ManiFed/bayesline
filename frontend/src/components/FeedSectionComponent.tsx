import type { FeedSection } from "../types";
import TopicCardComponent from "./TopicCardComponent";

interface Props {
  section: FeedSection;
  onSelectTopic: (id: string) => void;
}

export default function FeedSectionComponent({ section, onSelectTopic }: Props) {
  if (section.items.length === 0) return null;

  return (
    <div className="feed-section">
      <div className="section-header">
        <div className={`section-indicator ${section.name}`} />
        <span className="section-title">{section.display_name}</span>
        <span className="section-desc">{section.description}</span>
      </div>
      {section.items.map((item) => (
        <TopicCardComponent
          key={item.card.id}
          card={item.card}
          onClick={() => onSelectTopic(item.card.id)}
        />
      ))}
    </div>
  );
}
