import { Component, type ReactNode } from "react";

/**
 * Error boundary specifically for an assistant message bubble. If the
 * markdown renderer or contact-card rendering throws on a malformed
 * Claude response, this catches it and shows a small fallback in place
 * of the bubble — the rest of the chat keeps working.
 *
 * React error boundaries must be class components; nothing in the
 * function-component world replaces this yet.
 */
interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class MessageErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error): void {
    // Log so we can grep for these in dev. In production this would
    // route to whatever observability we wire up later.
    console.error("Message render error:", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex justify-start">
          <div className="max-w-[85%] rounded border border-din-red/40 bg-din-red/5 px-4 py-2 text-xs italic text-din-red dark:border-din-red-soft/40 dark:text-din-red-soft">
            (message failed to render)
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
