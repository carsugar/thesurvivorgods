import { parseSlashCommandOptions } from "./utils";

const CORRECT_ANSWER = [
  "Spider Silk",
  "Crushed Ruby",
  "Ashes of a Cursed Scroll",
  "Enchanted Apple Slice",
  "Mist of the Forgotten",
  "Unicorn Hair",
  "Dragon’s Blood Resin",
  "Smoldering Coal",
  "Thorn Vine",
  "Liquid Moonlight",
];

export const evaluateAnswer = async (interaction) => {
  const {
    item1,
    item2,
    item3,
    item4,
    item5,
    item6,
    item7,
    item8,
    item9,
    item10,
  } = parseSlashCommandOptions(interaction.data.options);

  const answer = [
    item1.value,
    item2.value,
    item3.value,
    item4.value,
    item5.value,
    item6.value,
    item7.value,
    item8.value,
    item9.value,
    item10.value,
  ];

  let evaluation = "";

  for (let i = 0; i <= answer.length; i++) {
    const item = answer[i];

    if (CORRECT_ANSWER[i] === item) {
      evaluation += `${item} :green_square: /n`;
    } else if (CORRECT_ANSWER.includes(item)) {
      evaluation += `${item} :yellow_square: /n`;
    } else {
      evaluation += `${item} :red_square: /n`;
    }
  }

  return evaluation.slice(0, evaluation.length - 1);
};
