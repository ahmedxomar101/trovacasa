"use client";

import { useState } from "react";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { Check, Pencil } from "lucide-react";

interface NotesEditorProps {
  listingId: string;
  initialNotes: string | null;
}

export function NotesEditor({ listingId, initialNotes }: NotesEditorProps) {
  const [notes, setNotes] = useState(initialNotes || "");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const router = useRouter();
  const supabase = createBrowserSupabaseClient();

  const save = async () => {
    setSaving(true);
    await supabase
      .from("listings")
      .update({ notes: notes || null })
      .eq("id", listingId);
    setSaving(false);
    setSaved(true);
    setEditing(false);
    setTimeout(() => setSaved(false), 2000);
    router.refresh();
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-zinc-300">Notes</h2>
        {!editing ? (
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1.5 text-sm text-zinc-400 hover:text-white transition-colors cursor-pointer min-h-[44px] min-w-[44px] justify-center touch-manipulation"
          >
            <Pencil size={16} />
            Edit
          </button>
        ) : (
          <button
            onClick={save}
            disabled={saving}
            className="flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors cursor-pointer disabled:opacity-50 min-h-[44px] min-w-[44px] justify-center touch-manipulation"
          >
            <Check size={16} />
            {saving ? "Saving\u2026" : "Save"}
          </button>
        )}
        {saved && (
          <span className="text-sm text-green-400 ml-2">Saved!</span>
        )}
      </div>

      {editing ? (
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Add your notes about this property\u2026"
          aria-label="Notes"
          className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-600 focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500 outline-none resize-y min-h-[100px]"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              save();
            }
          }}
        />
      ) : notes ? (
        <p className="text-sm text-zinc-400 whitespace-pre-wrap leading-relaxed">
          {notes}
        </p>
      ) : (
        <p className="text-sm text-zinc-600 italic">
          No notes yet. Click Edit to add notes.
        </p>
      )}
    </div>
  );
}
