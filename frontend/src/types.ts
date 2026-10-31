export type Fields = {
  person: string;
  engagement: string;
  start: string;
  end_inclusive: string;
  hours: number;
  warnings: string[];
};
export type Block =
  | { type: "text"; text: string }
  | {
      type: "table";
      block_id: string;
      title: string;
      columns: { key: string; label: string; unit?: string }[];
      rows: Record<string, string | number | boolean | null>[];
      completeness?: Record<string, unknown>;
    }
  | {
      type: "sql";
      query_id: string;
      purpose: string;
      sql: string;
      parameters: Record<string, unknown>;
    }
  | {
      type: "confirmation";
      action_id: string;
      status: "pending" | "confirmed" | "rejected" | "superseded";
      fields: Fields;
      booking_id: number | null;
    };
export type Answer = {
  thread_id: string;
  request_id: string;
  request_status: string;
  blocks: Block[];
  issues: { code: string; message: string; stage: string }[];
  assumptions: string[];
};
export type History = {
  thread_id: string;
  messages: {
    message_id: string;
    role: "user" | "assistant";
    content: string | Answer;
  }[];
  requests: { request_id: string; status: string; error: string | null }[];
  pending_action: {
    action_id: string;
    status: "pending";
    fields: Fields;
    booking_id: null;
  } | null;
  effective_reference_date: string;
};
export type Thread = {
  thread_id: string;
  label: string | null;
  updated_ts: number;
};
