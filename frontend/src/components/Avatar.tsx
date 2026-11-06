/** The bot's profile picture (the chef bot, public/bot-avatar.svg). It keeps its own colours in every theme. */
export function Avatar({ size }: { size: "sm" | "md" | "xl" }) {
  const px = { sm: 30, md: 40, xl: 88 }[size];
  return <img className={`avatar ${size}`} src="/bot-avatar.svg" alt="" width={px} height={px} />;
}
