import discord
from database import add_multiple_trigger_words

class AddMultipleWordsModal(discord.ui.Modal, title='Add Multiple Words'):
    words_input = discord.ui.TextInput(
        label='Words to Watch',
        placeholder='Enter words separated by commas (e.g., meeting, urgent, help)',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Parse the input
        words_list = [word.strip() for word in self.words_input.value.split(',')]
        words_list = [w for w in words_list if w]  # Remove empty strings
        
        if not words_list:
            await interaction.response.send_message("No valid words provided!", ephemeral=True)
            return
        
        # Add words to database
        added, duplicates = add_multiple_trigger_words(interaction.user.id, words_list)
        
        # Build response message
        response_parts = []
        
        if added:
            response_parts.append(f"**Added {len(added)} word(s):** {', '.join(f'`{w}`' for w in added)}")
        
        if duplicates:
            response_parts.append(f"**Already watching:** {', '.join(f'`{w}`' for w in duplicates)}")
        
        if not added and not duplicates:
            response_parts.append("No words were added.")
        
        await interaction.response.send_message('\n'.join(response_parts), ephemeral=True)
        print(f"User {interaction.user.name} added multiple words: {added}")
