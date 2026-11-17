import { useRef, useState, type DragEvent } from "react";

const carriesFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");

/** Drag and drop of an image onto an area: spread `bind` on the area's element. `dragging` is true while a file is held
 *  over it (to show a "drop here" hint). Counts enter/leave pairs, because moving over a child fires a leave on the
 *  parent. Dropping anything that is not an image does nothing (and the browser does not open it in place of the app). */
export function useImageDrop(onImage: (file: File) => void, enabled = true) {
  const [dragging, setDragging] = useState(false);
  const depth = useRef(0);

  const reset = () => {
    depth.current = 0;
    setDragging(false);
  };

  const bind = {
    onDragEnter: (e: DragEvent) => {
      if (!enabled || !carriesFiles(e)) return;
      e.preventDefault();
      depth.current++;
      setDragging(true);
    },
    onDragOver: (e: DragEvent) => {
      if (!enabled || !carriesFiles(e)) return;
      e.preventDefault();                                   // required, or the drop is refused
      e.dataTransfer.dropEffect = "copy";
    },
    onDragLeave: (e: DragEvent) => {
      if (!enabled || !carriesFiles(e)) return;
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setDragging(false);
    },
    onDrop: (e: DragEvent) => {
      if (!enabled || !carriesFiles(e)) return;
      e.preventDefault();
      reset();
      const file = Array.from(e.dataTransfer.files).find((f) => f.type.startsWith("image/"));
      if (file) onImage(file);
    },
  };
  return { dragging: enabled && dragging, bind };
}
